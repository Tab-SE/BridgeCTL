import os
from pathlib import Path

from src import download_util
from src import models
from src.bridge_logs import BridgeContainerLogsPath
from src.bridge_rpm_download import BridgeRpmDownload
from src.docker_client import DockerClient, ContainerLabels
from src.driver_caddy.driver_script_generator import DriverScriptGenerator
from src.models import (
    LoggerInterface,
    AppSettings,
    BridgeImageName,
    BridgeRpmSource,
    BridgeRequest,
    DiskLogger,
)

buildimg_path = f"{Path(__file__).parent.parent}{os.sep}buildimg"
buildimg_drivers_path = Path(buildimg_path) / "drivers"
bridge_client_config_filename = "TabBridgeClientConfiguration.txt"
bridge_client_config_path = Path(buildimg_path) / bridge_client_config_filename


class BridgeContainerBuilder:
    def __init__(self, logger: LoggerInterface, req: models.BridgeRequest):
        self.logger: LoggerInterface = DiskLogger(logger, "build")
        self.req: BridgeRequest = req
        self.docker_client = DockerClient(self.logger)
        self.rpm_download = BridgeRpmDownload(
            self.logger, self.req.bridge.bridge_rpm_source, buildimg_path
        )
        self.driver_script_generator = DriverScriptGenerator(self.logger, buildimg_path)
        if not os.path.exists(buildimg_path):
            os.mkdir(buildimg_path)
        if not buildimg_drivers_path.exists():
            buildimg_drivers_path.mkdir()

    @classmethod
    def set_runas_user(cls, req, dockerfile_elements: dict):
        if req.bridge.user_as_tableau:
            dockerfile_elements[
                "#<USER_CREATE>"
            ] = f"""RUN groupadd --system --gid 1053 tableau && \\
    adduser --system --create-home --gid 1053 --uid 1053 --shell /bin/bash --home /home/tableau tableau
ENV HOME=/home/tableau
RUN chown -R tableau:tableau /bridge_setup"""
            dockerfile_elements["#<USER_NAME>"] = "tableau"
        else:
            dockerfile_elements["#<USER_CREATE>"] = ""
            dockerfile_elements["#<USER_NAME>"] = "root"

    @staticmethod
    def bridge_repo_path(req: BridgeRequest):
        home_path = "/home/tableau" if req.bridge.user_as_tableau else "/root"
        beta = "_Beta" if req.bridge.bridge_rpm_source == BridgeRpmSource.devbuilds else ""
        bridge_folder = f"{home_path}/Documents/My_Tableau_Bridge_Repository{beta}"
        return bridge_folder

    def build_bridge_image(self):
        self.logger.info("Build Tableau Bridge Docker Image")
        if not self.docker_client.is_docker_available():
            return
        if not os.path.exists(buildimg_path):
            os.mkdir(buildimg_path)
        req: BridgeRequest = self.req
        self.logger.info(f"working folder: {buildimg_path}")

        self.logger.info("STEP - Download Bridge RPM")
        if req.bridge.only_db_drivers:
            rpm_file = "n/a, drivers only"
        else:
            rpm_file = self.rpm_download.route_download_request_for_bridge_rpm(req)
            if rpm_file is None:
                self.logger.error(
                    f"INVALID: Bridge rpm file not found in {buildimg_path}"
                )
                return False

            self.logger.info(f"using local rpm file: {rpm_file}")
        if not self.req.bridge.use_minerva():
            sub_run = {"tableau_bridge/bin/run-bridge.sh": "tableau_bridge/bin/TabBridgeClientWorker"}
        else:
            sub_run = None
        download_util.write_template(
            f"{Path(__file__).parent}/templates/start-bridgeclient.sh",
            f"{buildimg_path}{os.sep}start-bridgeclient.sh",
            True,
            replace=sub_run,
        )

        if bridge_client_config_path.exists():
            self.logger.info(f"STEP - copy custom {bridge_client_config_filename} into image")
            if req.bridge.user_as_tableau:
                br_client_conf_copy = f"""
RUN mkdir -p {self.bridge_repo_path(req)}/Configuration && \\
  chown -R tableau:tableau {self.bridge_repo_path(req)} && \\
  chmod -R 755 {self.bridge_repo_path(req)}
COPY TabBridgeClientConfiguration.txt {self.bridge_repo_path(req)}/Configuration/
RUN chown tableau:tableau {self.bridge_repo_path(req)}/Configuration/TabBridgeClientConfiguration.txt && \\
    chmod 644 {self.bridge_repo_path(req)}/Configuration/TabBridgeClientConfiguration.txt
"""
            else:
                br_client_conf_copy = f"COPY {bridge_client_config_filename} {self.bridge_repo_path(req)}/Configuration/\n"
        else:
            br_client_conf_copy = ""

        # STEP - Locale setup
        locale_setup_script = ""
        if req.bridge.locale:
            locale_setup_script = f"RUN yum install -y glibc-langpack-en\n" \
                        "ENV LANG=en_US.UTF-8 \\\n    LANGUAGE=en_US:en \\\n    LC_ALL=en_US.UTF-8"
            self.logger.info(f"setting locale to: {self.req.bridge.locale}")

        self.logger.info("STEP - Drivers")
        drivers_str = ",".join(req.bridge.include_drivers)
        self.logger.info(f"drivers to install: {drivers_str}")
        copy_driver_files = self.driver_script_generator.gen(
            req.bridge.include_drivers, req.bridge.linux_distro, True
        )
        copy_str = ""
        for d in copy_driver_files:
            copy_str += f"COPY ./drivers/{d} /tmp/driver_caddy/\n"
        copy_str = copy_str.rstrip()

        # STEP - Write Dockerfile
        dockerfile_elements = {
            "#<FROM_BASEIMAGE>": req.bridge.base_image,
            "#<COPY_DRIVER_FILES>": copy_str,
            "#<COPY_BridgeClientConfiguration>": br_client_conf_copy,
            "#<Locale_Setup>": locale_setup_script,
        }
        self.set_runas_user(req, dockerfile_elements)

        docker_file = (
            "Dockerfile_drivers_only" if req.bridge.only_db_drivers else "Dockerfile"
        )
        download_util.write_template(
            f"{Path(__file__).parent}/templates/{docker_file}",
            f"{buildimg_path}/Dockerfile",
            replace=dockerfile_elements,
        )

        labels = {
            ContainerLabels.database_drivers: drivers_str,
            ContainerLabels.tableau_bridge_rpm_version: rpm_file,
            ContainerLabels.tableau_bridge_rpm_source: req.bridge.bridge_rpm_source,
            ContainerLabels.base_image_url: req.bridge.base_image,
            ContainerLabels.tableau_bridge_logs_path: BridgeContainerLogsPath.get_logs_path(
                req.bridge.bridge_rpm_source, req.bridge.user_as_tableau
            ),
        }
        is_release = req.bridge.bridge_rpm_source == BridgeRpmSource.tableau_com
        self.logger.info("STEP - Build Docker image")
        docker_nocache = True
        build_args = {
            "BRIDGERPM": rpm_file,
            "IS_RELEASE": str(is_release).lower()
        }
        local_image_name = BridgeImageName.local_image_name(self.req)
        self.logger.info(f"image name: {local_image_name}")
        self.logger.info("this will take a few minutes ...")
        logs = self.docker_client.run_build_bridge_image(
            local_image_name, buildimg_path, build_args, labels, docker_nocache
        )

        if logs:
            for line in logs:
                self.logger.info(line.get("stream"))
            return True
        else:
            return False

class BridgeBuildState:
    is_building = False

BRIDGE_BUILD_STATE = BridgeBuildState()
