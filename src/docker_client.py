import json
import os
import platform
import tempfile
import re
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import List
from datetime import datetime

import docker
from docker.errors import NotFound, DockerException, APIError
from docker.models.containers import Container
from docker.models.images import Image

from src.enums import AMD64_PLATFORM, SCRATCH_DIR
from src.lib.general_helper import FileHelper, StringUtils
from src.models import LoggerInterface, BridgeImageName
from src.os_type import current_os, OsType


class ContainerLabels:
    tableau_bridge_agent_name = "tableau_bridge_agent_name"
    tableau_sitename = "tableau_sitename"
    tableau_server_url = "tableau_server_url"
    tableau_pool_name = "tableau_pool_name"
    tableau_pool_id = "tableau_pool_id"
    database_drivers = "database_drivers"
    # database_drivers_additional = "database_drivers_additional"
    tableau_bridge_rpm_version = "tableau_bridge_rpm_version"
    base_image_url = "base_image_url"
    tableau_bridge_rpm_source = "tableau_bridge_rpm_source"
    linux_distro = "linux_distro"
    tableau_bridge_logs_path = "tableau_bridge_logs_path"
    user_as_tableau = "user_as_tableau"


@dataclass
class ContainerDetails:
    cpu_usage_pct: float = 0
    mem_usage_mb: float = 0
    disk_usage: str = ""
    image_name: str = None
    labels: dict = None
    status: str = None
    started: str = None
    started_ago: str = None
    jdbc_drivers = ""
    odbc_drivers = ""
    volume_mounts = None
    network_mode = None
    image_create_date = None

    def name(self):
        return self.labels.get(ContainerLabels.tableau_bridge_agent_name)

    def get_serializable(self) -> dict:
        labels = self.labels
        labels = {
            k: str(labels.get(k))
            for k in ContainerLabels.__dict__.values()
            if labels.get(k)
        }
        return {
            "image_name": self.image_name,
            "status": self.status,
            "started": str(self.started),
            "jdbc_drivers": self.jdbc_drivers,
            "odbc_drivers": self.odbc_drivers,
            "image_create_date": str(self.image_create_date),
            "labels": labels,
        }


@dataclass
class ImageDetail:
    short_id: str = None
    image_name: str = None
    labels: dict = None
    tags: List[str] = None
    tableau_bridge_rpm_version: str = None
    tableau_bridge_rpm_source: str = None
    database_drivers: str = None
    base_image_url: str = None
    size_gb: int = 0
    created: str = None
    used_by_containers: List[str] = None


class TempLogsSettings:
    temp_bridge_logs_path = SCRATCH_DIR / "temp_bridge_logs"

    def create_path(self):
        if not self.temp_bridge_logs_path.exists():
            self.temp_bridge_logs_path.mkdir(parents=True, exist_ok=True)


class TempCacheDir:
    def __init__(self):
        tempdir = Path(
            "/tmp" if platform.system() == "Darwin" else tempfile.gettempdir()
        )
        self.tmp_path = os.path.join(tempdir, "bridgectl")
        if not os.path.isdir(self.tmp_path):
            os.makedirs(self.tmp_path, exist_ok=True)


# one_time_check_docker = None


class DockerClient:
    bridge_prefix = "bridge"

    def __init__(self, logger: LoggerInterface):
        self.logger = logger

    def is_docker_available(self) -> bool:
        """
        Check if docker is installed and running with OsType=linux.
        """
        try:
            client = docker.from_env()
            client.version()
            if current_os() != OsType.win:
                return True
            docker_os_type = client.info().get("OSType")
            if docker_os_type == "linux":
                return True
            else:
                self.logger.error(
                    f"ERROR: Docker OSType = {docker_os_type} which is not supported for building bridge linux images."
                )
                return False
        except DockerException as ex:
            self.logger.error(f"ERROR: Docker not ready on host. Please start it. {ex}")
            self.show_install_info()
            return False

    def get_containers_list(self, name_prefix=None) -> List[Container]:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        if name_prefix:
            containers = [c for c in containers if c.name.startswith(name_prefix)]
        return containers

    def get_bridge_container_names(self):
        return self.get_container_names(self.bridge_prefix)

    def get_container_names(self, name_prefix=None):
        containers = self.get_containers_list(name_prefix)
        names = []
        for c in containers:
            names.append(c.name)
        names.sort()
        return names

    def get_container_by_name(self, name):
        client = docker.from_env()
        try:
            container = client.containers.get(name)
            return container
        except NotFound:
            return None

    def stop_and_remove_container(self, name):
        client = docker.from_env()
        container = client.containers.get(container_id=name)
        self.logger.info(f"stopping container {name}")
        container.stop()
        self.logger.info(f"removing container {name}")
        container.remove(force=True)

    def get_stdout_logs(self, name):
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=name)
            logs = container.logs(timestamps=True)
            return logs.decode("utf-8")
        except NotFound:
            self.logger.error(f"Container not found: {name}")
        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
        finally:
            client.close()

    def get_all_bridge_logs_as_tar(self, name):
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=name)
            logs_path = container.labels[ContainerLabels.tableau_bridge_logs_path]
            bits, _ = container.get_archive(logs_path, encode_stream=True)
            tmp_file = tempfile.NamedTemporaryFile(delete=False)
            with open(tmp_file.name, "wb") as f:
                for chunk in bits:
                    f.write(chunk)
            return tmp_file.name
        except NotFound:
            self.logger.error(f"Container not found: {name}")
        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
        finally:
            client.close()

    def search_all_logs_for_text(self, name: str, search_text: str, max_records: int = 10000) -> List[dict]: #FutureDev: finish implementation
        """Search through all log files in the container for given text.
        
        Args:
            name: Container name
            search_text: Text to search for
            max_records: Maximum number of records to return (default 10000)
            
        Returns:
            List of matching log entries or None if error
        """
        client = docker.from_env()
        try:
            container = client.containers.get(name)
            logs_path = container.labels.get(ContainerLabels.tableau_bridge_logs_path)
            if not logs_path:
                raise Exception(f"Container does not have label {ContainerLabels.tableau_bridge_logs_path}")

            # Create search script
            script = f"""
                #!/bin/bash
                set -e
                
                # Initialize output file
                echo "[]" > /tmp/bridge_logs_search.json
                
                # Find all files in log directory, sort by modification time (newest first)
                find {logs_path} -type f -printf "%T@ %p\\n" | sort -nr | cut -d' ' -f2- | while read -r file; do
                    # Skip if not a regular file
                    [ ! -f "$file" ] && continue
                    
                    # Process each line
                    while IFS= read -r line; do
                        if echo "$line" | grep -q "{search_text}"; then
                            # Try to parse as JSON
                            if echo "$line" | jq . >/dev/null 2>&1; then
                                # Add filename field and append to results
                                echo "$line" | jq --arg file "$file" '. + {{"filename": $file}}' >> /tmp/bridge_logs_search.json
                                
                                # Check record count
                                count=$(wc -l < /tmp/bridge_logs_search.json)
                                if [ $count -ge {max_records} ]; then
                                    break 2
                                fi
                            fi
                        fi
                    done < "$file"
                done
            """

            # Write and execute search script
            exit_code, output = container.exec_run(
                cmd=["bash", "-c", script],
                environment={"LANG": "C.UTF-8"},
                workdir="/tmp"
            )
            
            if exit_code != 0:
                self.logger.error(f"Search script failed: {output.decode()}")
                return None
                
            # Get results file from container
            # bits, stat = container.get_archive("/tmp/bridge_logs_search.json")
            
            # # Write to local temp file
            # tmp_file = Path(tempfile.gettempdir()) / "bridge_logs_search.json"
            # with open(tmp_file, "wb") as f:
            #     for chunk in bits:
            #         f.write(chunk)
                
            # # Read and parse results
            # with open(tmp_file) as f:
            #     results = [json.loads(line) for line in f if line.strip()]
                
            # self.logger.info(f"Found {len(results)} matching records")
            # return results

        except Exception as e:
            self.logger.error(f"Error searching logs: {str(e)}")
            return None
        finally:
            client.close()

    def list_tableau_container_log_filenames(self, name):
        client = docker.from_env()
        try:
            container = client.containers.get(name)
            logs_path = container.labels.get(ContainerLabels.tableau_bridge_logs_path)
            if not logs_path:
                raise Exception(
                    f"container does not have label {ContainerLabels.tableau_bridge_logs_path}"
                )
            cmd = f'sh -c \'if [ -d {logs_path} ]; then find {logs_path} -maxdepth 1 -type f -printf "%f\\n"; else echo "Error: Directory does not exist."; exit 2; fi\''
            exit_code, out = container.exec_run(cmd=cmd, stderr=True)
            out = out.decode("utf-8")
            if exit_code != 0:
                self.logger.error(
                    f"Error getting logs from container path {logs_path}. Error: {out}"
                )
                return None

            log_filenames = out.split("\n")
            # log_filenames.sort()
            # log_filenames = [
            #     x
            #     for x in log_filenames
            #     if not (
            #         x.startswith("hyperd")
            #         or x.startswith("jproto")
            #         or x.endswith(".txt")
            #     )
            # ]
            return log_filenames
        except NotFound:
            self.logger.error(f"Container not found: {name}")
        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
        finally:
            client.close()

    def download_single_file_to_disk(
        self, container_name: str, logfile_name: str, is_client_config: bool = False
    ):
        client = docker.from_env()
        try:
            container = client.containers.get(container_name)
            TempLogsSettings().create_path()
            logs_path = container.labels.get(ContainerLabels.tableau_bridge_logs_path)
            if not logs_path:
                raise Exception(
                    f"container does not have label {ContainerLabels.tableau_bridge_logs_path}"
                )
            if is_client_config:
                logs_path = logs_path.replace("/Logs", "/Configuration")
            bits, _ = container.get_archive(f"{logs_path}/{logfile_name}")
            tmp_tar = TempLogsSettings.temp_bridge_logs_path / f"{logfile_name}.tar"
            with open(tmp_tar, "wb") as f:
                for chunk in bits:
                    f.write(chunk)
            tmp_text_file = TempLogsSettings.temp_bridge_logs_path / logfile_name
            FileHelper.extract_single_tar_content_to_text(tmp_tar, tmp_text_file)
            tmp_tar.unlink()
            return str(tmp_text_file)
        finally:
            client.close()

    def calc_cpu_usage_pct(self, stats):
        if not stats.get("cpu_stats") or not stats.get("precpu_stats"):
            return 0
        try:
            cpu_delta = float(
                stats["cpu_stats"].get("cpu_usage", {}).get("total_usage", 0)
                - stats["precpu_stats"].get("cpu_usage", {}).get("total_usage", 0)
            )
            system_delta = float(
                stats["cpu_stats"].get("system_cpu_usage", 0)
                - stats["precpu_stats"].get("system_cpu_usage", 0)
            )
            online_cpus = float(stats["cpu_stats"].get("online_cpus", 0))
            if system_delta == online_cpus == 0:
                return 0
            return (cpu_delta / system_delta) * online_cpus * 100.0
        except Exception as ex:
            self.logger.warning(ex)
            return 0

    def get_image_details(self, image_name) -> ImageDetail:
        client = docker.from_env()
        image: Image
        try:
            image = client.images.get(image_name)
        except NotFound:
            return None
        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
            return None
        finally:
            client.close()
        img_detail = ImageDetail()
        img_detail.labels = image.labels
        img_detail.tableau_bridge_rpm_version = image.labels.get(
            ContainerLabels.tableau_bridge_rpm_version
        )
        img_detail.tableau_bridge_rpm_source = image.labels.get(
            ContainerLabels.tableau_bridge_rpm_source
        )
        img_detail.database_drivers = image.labels.get(ContainerLabels.database_drivers)
        img_detail.base_image_url = image.labels.get(ContainerLabels.base_image_url)
        img_detail.size_gb = round(image.attrs.get("Size", 0) / (1024**3), 1)
        img_detail.created = image.attrs.get("Created", "")
        img_detail.short_id = image.short_id.replace("sha256:", "")
        img_detail.image_name = image_name
        img_detail.tags = image.tags
        img_detail.used_by_containers = self.is_image_in_use(image_name)
        if img_detail.used_by_containers:
            img_detail.used_by_containers = ", ".join(img_detail.used_by_containers)
        return img_detail

    def image_exists(self, image_name: str) -> bool:
        img = self.get_image_details(image_name)
        return bool(img)

    def is_image_in_use(self, image_name: str) -> List[str]:
        client = docker.from_env()
        try:
            containers = client.containers.list(all=True)
            used_by = []
            for container in containers:
                if container.image.tags and image_name in container.image.tags:
                    used_by.append(container.name)
            return used_by
        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
            return []
        finally:
            client.close()

    def remove_image(self, image_name: str) -> bool:
        client = docker.from_env()
        containers = self.is_image_in_use(image_name)
        if containers:
            self.logger.error(f"Image {image_name} is in use. First remove the containers: {', '.join(containers)}")
            return False
        try:
            image = client.images.get(image_name)
            client.images.remove(image.id, force=True) # removes all tags for image and deletes the image. (sometimes leaves a dangling image which can be cleaned up by `docker system prune`)
            return True
        except NotFound:
            self.logger.warning(f"Image not found: {image_name}")
            return False
        except APIError as e:
            self.logger.error(f"Docker API error during image removal: {e}")
            return False
        finally:
            client.close()

    def get_container_details(self, container_name: str, include_hardware_stats: bool) -> ContainerDetails:
        client = docker.from_env()
        container: Container
        try:
            container = client.containers.get(container_id=container_name)
        except NotFound:
            self.logger.error(f"Container not found: {container_name}")
            return None
        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
            return None
        finally:
            client.close()
        details = ContainerDetails()
        details.status = container.status
        details.labels = container.labels
        image_tags = container.image.attrs.get("RepoTags")
        dte = container.image.attrs.get("Created", "")
        details.image_create_date = StringUtils.parse_time_string(dte)
        details.image_name = image_tags[0] if image_tags else None
        if container.attrs.get("Mounts"):
            details.volume_mounts = []
            for m in container.attrs.get("Mounts"):
                details.volume_mounts.append(f"{m['Source']} => {m['Destination']}")
        details.network_mode = container.attrs.get("HostConfig", {}).get("NetworkMode")
        if include_hardware_stats:
            stats = container.stats(stream=False)
            if container.status == "running":
                if not details.volume_mounts:
                    ext_code, du_logs = container.exec_run(cmd="du -sh /", stderr=False)
                    details.disk_usage = du_logs.decode("utf-8").split("\t")[0]
                else:
                    details.disk_usage = "N/A (mounted disk)"
                details.started = container.attrs.get("State", {}).get("StartedAt", "")
                started_time = StringUtils.parse_time_string(details.started)
                details.started_ago = StringUtils.short_time_ago(started_time)
                self.inspect_drivers(container, details)
            details.cpu_usage_pct = self.calc_cpu_usage_pct(stats)
            details.mem_usage_mb = (
                stats.get("memory_stats", {}).get("usage", 0) / 1024 / 1024
            )
        return details

    def run_build_bridge_image(self, bridge_image_name: str, buildimg_path: str, build_args: dict, labels: dict, nocache: bool = True):
        client = docker.from_env()
        try:
            tag_val = f"{bridge_image_name}:latest"
            image, logs = client.images.build(
                path=buildimg_path,
                buildargs=build_args,
                quiet=False,
                labels=labels,
                nocache=nocache,
                platform=AMD64_PLATFORM,
                tag=tag_val
            )
            return logs
        except Exception as e:
            if hasattr(e, 'build_log'):
                for log in e.build_log:
                    if "stream" in log:
                        self.logger.info(log["stream"])
                    elif "error" in log:
                        self.logger.warning(log["error"])
                    else:
                        self.logger.warning(str(log))
            else:
                self.logger.error(f"Docker Image build error: {e}") #do we need to look at a different attribute for error details?
            return None
        finally:
            client.close()

    def run_bridge_container(
        self,
        image_id,
        container_name,
        labels,
        env_vars,
        volumes,
        dns_mappings,
        network_mode,
    ):
        client = docker.from_env()
        container = client.containers.run(
            image_id,
            labels=labels,
            detach=True,
            name=container_name,
            volumes=volumes,
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 1},
            extra_hosts=dns_mappings,
            environment=env_vars,
            network_mode=network_mode,
        )
        return container

    def restart_container(self, name):
        client = docker.from_env()
        container = client.containers.get(container_id=name)
        container.restart()

    def edit_client_config_v2(self, container_name: str, client_config: dict):
        client = docker.from_env()
        container = client.containers.get(container_name)
        logs_path = container.labels.get(ContainerLabels.tableau_bridge_logs_path)
        if not logs_path:
            raise Exception(
                f"container does not have label {ContainerLabels.tableau_bridge_logs_path}"
            )
        config_path = logs_path.replace("/Logs", "/Configuration")
        config_file = f"{config_path}/TabBridgeClientConfiguration.txt"
        json_content = json.dumps(client_config, indent=4)

        cmd = f"""sh -c 'cat > {config_file} << "EOF"
{json_content}
EOF'"""

        out = None
        for i in range(0, 1):
            exit_code, out = container.exec_run(cmd=cmd)
            if exit_code == 0:
                return True, out.decode("utf-8")
            self.logger.info(f"retrying ... attempt {i + 1}")
            sleep(2)
        return False, out.decode("utf-8")

    def get_docker_info(self):
        """
        call `docker info` and return the output
        """
        import subprocess

        try:
            output = subprocess.check_output("docker info", shell=True)
            return output.decode("utf-8")
        except subprocess.CalledProcessError:
            return "Docker is not installed or not running properly."

    def inspect_drivers(self, container, details: ContainerDetails):
        jdbc_exec = container.exec_run("ls /opt/tableau/tableau_driver/jdbc")
        jdbc_exec_output = jdbc_exec.output.decode("utf-8").strip()
        if "No such file" not in jdbc_exec_output:
            details.jdbc_drivers = jdbc_exec_output.replace("\n", ", ")

        odbc_exec = container.exec_run("odbcinst -q -d")
        # odbc_exec2 = container.exec_run("cat /etc/odbcinst.ini")
        odbc_exec_output = odbc_exec.output.decode("utf-8")
        if "No such file" not in odbc_exec_output:
            # installed_drivers = re.findall(r"\[(.*?)\]", odbc_exec_output)
            # details.odbc_drivers = ", ".join(installed_drivers)
            details.odbc_drivers = odbc_exec_output.replace("\n", " ")

    def test_db_connection(self, name, cmd):
        client = docker.from_env()
        container = client.containers.get(container_id=name)
        exit_code, out = container.exec_run(cmd=cmd)
        return exit_code, out.decode("utf-8")

    def get_tableau_bridge_image_names(self):
        client = docker.from_env()
        images = client.images.list()
        image_names = []
        for img in images:
            if img.tags:
                t = img.tags[-1] # we are looking the last tag. but we might need to change this logic to look at all tags.
                if t.startswith(BridgeImageName.tableau_bridge_prefix) or f":{BridgeImageName.tableau_bridge_prefix}" in t:
                    image_names.append(t)
        return image_names

    def show_install_info(self):
        if current_os() not in [OsType.win, OsType.linux, OsType.mac]:
            return

        self.logger.info(
            "If docker is not installed on the machine please follow the link below:"
        )
        if current_os() == OsType.linux:
            self.logger.info("Ubuntu: https://docs.docker.com/engine/install/ubuntu/")
            self.logger.info("Red Hat: https://docs.docker.com/engine/install/rhel/")
        elif current_os() == OsType.mac:
            self.logger.info(
                "https://docs.docker.com/desktop/setup/install/mac-install/"
            )
        elif current_os() == OsType.win:
            self.logger.info(
                "https://docs.docker.com/desktop/setup/install/windows-install/"
            )
