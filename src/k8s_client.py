import io
import os
import re
from dataclasses import dataclass
from base64 import b64decode, b64encode
from datetime import datetime
from pathlib import Path
from typing import List

from kubernetes import client, config, stream
from kubernetes.client.rest import ApiException
import yaml

from src.bridge_logs import BridgeContainerLogsPath
from src.docker_client import TempLogsSettings, ContainerLabels
from src.lib.general_helper import FileHelper, StringUtils


class K8sSettings:
    kube_config_folder: str = os.path.expanduser('~/.kube')
    kube_config_path: str = os.path.expanduser('~/.kube/config')

    @classmethod
    def does_kube_config_exist_with_warning(cls, st = None):
        exists = cls.does_kube_config_exist()
        if not exists and st:
            st.warning("kube_config.yaml not been configured in [Settings](/Settings?tab=k8s)")
            st.stop()
        return exists

    @staticmethod
    def does_kube_config_exist():
        return os.path.exists(K8sSettings.kube_config_path)

    @staticmethod
    def get_current_k8s_context_name() -> (str, str):
        if not K8sSettings.does_kube_config_exist():
            return None, None
        with open(K8sSettings.kube_config_path, 'r') as yaml_file:
            k_yml = yaml.safe_load(yaml_file)
        current_context_name = k_yml.get('current-context')
        if not current_context_name:
            return None, None

        server_url = None
        for c in k_yml.get('clusters', []):
            if c["name"] == current_context_name:
                server_url = c['cluster']['server']
                break
        return current_context_name, server_url

    @classmethod
    def delete_kube_config(cls):
        if os.path.exists(cls.kube_config_path):
            os.remove(cls.kube_config_path)

    @classmethod
    def backup_kube_config(cls):
        if cls.does_kube_config_exist():
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{cls.kube_config_path}_{date_str}.bak"
            with open(backup_path, 'wb') as f:
                f.write(open(cls.kube_config_path, 'rb').read())

    @classmethod
    def save_kube_config(cls, value):
        if not os.path.exists(cls.kube_config_folder):
            os.mkdir(cls.kube_config_folder)
        with open(K8sSettings.kube_config_path, 'wb') as f:
            f.write(value)


@dataclass
class K8sPod:
    name: str
    phase: str
    creation_timestamp: datetime
    started_at: datetime
    labels: dict
    namespace: str
    image_url: str
    created_ago: str = None
    started_ago: str = None
    status: str = None

class K8sClient:
    def __init__(self):
        if not K8sSettings.does_kube_config_exist():
            raise Exception(f"Kube config file not found at {K8sSettings.kube_config_path}")
        self.config_file = K8sSettings.kube_config_path
        config.load_kube_config(config_file=self.config_file)
        self.client = client.CoreV1Api()

    def namespace_exists(self, namespace):
        """Return True if namespace exists, False otherwise."""
        try:
            api_response = self.client.read_namespace_status(namespace)
            return True if api_response else False
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return False
            else:
                raise e

    def check_config_has_correct_cluster_name(self, cluster_name):
        """Check that the current kube context matches the expected cluster_name."""
        with open(self.config_file, 'r') as yaml_file:
            k_yml = yaml.safe_load(yaml_file)
        if not k_yml['current-context'] == cluster_name:
            raise Exception(f"current kube context does not match expected cluster_name {cluster_name} in {self.config_file}")

    def check_connection(self):
        """Check the connection to the Kubernetes cluster and return a ConnectResult object."""
        ret = ConnectResult()
        try:
            namespaces = self.client.list_namespace()
            ret.can_connect = True
        except Exception as e:
            ret.error = str(e)
        return ret

    def read_secret(self, secret_name: str, namespace: str):
        """Read and return the value of the specified secret in the given namespace."""
        value = self.client.read_namespaced_secret(secret_name, namespace)
        if not value or not value.data:
            return '{}'
        by = b64decode(value.data.get('pat'))
        d = by.decode('ascii')
        # convert string dictionary to dict
        d = eval(d)

        return d

    def write_secret(self, secret_name: str, secret_value: str, namespace: str):
        """Write the given secret value to the specified secret in the given namespace."""
        body = self.client.read_namespaced_secret(secret_name, namespace)
        if not body.data:
            body.data = {}
        body.data[secret_name] = b64encode(secret_value.encode('ascii')).decode('ascii')
        self.client.replace_namespaced_secret(secret_name, namespace, body)

    def create_secret_if_not_exists(self, namespace: str, secret_name: str, secret_data: str = ""):
        # Futuredev: Maybe it should update existing secret if exists
        """Create the specified secret in the given namespace if it does not exist."""
        secret_name = self.normalize_k8s_name(secret_name)
        try:
            _ = self.client.read_namespaced_secret(secret_name, namespace)
        except ApiException as ex:
            if ex.status == 404:
                body = client.V1Secret()
                body.api_version = 'v1'
                body.data = {
                    secret_name: b64encode(secret_data.encode('ascii')).decode('ascii')
                }
                body.kind = 'Secret'
                body.metadata = {'name': secret_name}
                body.type = 'Opaque'
                self.client.create_namespaced_secret(namespace, body)
            else:
                raise ex

    @staticmethod
    def normalize_k8s_name(name: str) -> str:
        return name.replace('_', '-')

    def get_pods_by_prefix(self, namespace: str, pod_prefix: str) -> List[K8sPod]:
        pods = self.client.list_namespaced_pod(namespace=namespace)
        if not pods.items:
            return []
        pods = [x for x in pods.items if not pod_prefix or pod_prefix in x.metadata.name]
        pod_list = []
        for pod in pods:
            p = K8sPod(
                name=pod.metadata.name,
                phase = pod.status.phase,
                creation_timestamp=pod.metadata.creation_timestamp,
                started_at=pod.status.start_time,
                labels=pod.metadata.labels,
                namespace=pod.metadata.namespace,
                image_url=pod.spec.containers[0].image
            )
            pod_list.append(p)
            p.created_ago = StringUtils.short_time_ago(p.creation_timestamp)
            p.started_ago = StringUtils.short_time_ago(p.started_at)
            if pod.metadata.deletion_timestamp:
                p.phase = "Terminating"
            if pod.status.container_statuses:
                p.status = pod.status.container_statuses[0].state
                # p.started_at = pod.status.container_statuses[0].state.running.started_at
            # if pod.status.container_statuses[0].state.running:
            #     p.status = "running"
            #     p.started_at = pod.status.container_statuses[0].state.running.started_at
            # elif pod.status.container_statuses[0].state.terminated:
            #     p.status = "terminated"
            # elif pod.status.container_statuses[0].state.waiting:
            #     p.status = "waiting"
            # else:
            #     p.status = "unknown"
            # if pod.metadata.deletion_timestamp:
            #     p.status = "terminating"
            # elif pod.status.phase in ["Pending", "Succeeded", "Failed", "Unknown"]:
            #     p.status = pod.status.phase.lower()
            # if "3" in p.name:
            #     print(pod)
        return pod_list

    def get_pod_names_by_prefix(self, namespace: str, pod_prefix: str) -> List[str]:
        pods = self.client.list_namespaced_pod(namespace=namespace)
        if not pods.items:
            return []
        return [x.metadata.name for x in pods.items if not pod_prefix or pod_prefix in x.metadata.name]

    # @classmethod
    # def decode_labels(cls, labels: dict):
    #     for k, v in labels.items():
    #         if k == ContainerLabels.tableau_bridge_logs_path:
    #             labels[k] = cls.decode_from_k8s_label(v)
    #             break

    def get_pod_detail(self, namespace: str, pod_prefix: str, pod_name: str) -> K8sPod:
        pods = self.get_pods_by_prefix(namespace, pod_prefix)
        for p in pods:
            if p.name == pod_name:
                # self.decode_labels(p.labels)
                return p
        return None

    def list_pod_log_filenames(self, namespace: str, pod_name: str) -> List[str]:
        detail = self.get_pod_detail(namespace, pod_name, pod_name)
        rpm_source = detail.labels[ContainerLabels.tableau_bridge_rpm_source]
        user_as_tableau = bool(detail.labels[ContainerLabels.user_as_tableau])
        logs_path = BridgeContainerLogsPath.get_logs_path(rpm_source, user_as_tableau)
        if detail.phase != "Running":
            return [], "Pod is not running"
        # if not logs_path:
        #     raise Exception(f"container does not have label {ContainerLabels.tableau_bridge_logs_path}")
        # logs_path = self.decode_from_k8s_label(logs_path)
        command = ["sh", "-c", f"find {logs_path} -maxdepth 1 -type f -printf '%f\n'"]
        #cmd = f"sh -c 'if [ -d {logs_path} ]; then find {logs_path} -maxdepth 1 -type f -printf \"%f\\n\"; else echo \"Error: Directory does not exist.\"; exit 2; fi'"

        resp = stream.stream(self.client.connect_get_namespaced_pod_exec, pod_name, namespace,
                             command=command,
                             stderr=True, stdin=False,
                             stdout=True, tty=False)
        if "No such file or directory" in resp:
            return [], None

        file_names = [f for f in resp.split("\n") if f]
        return file_names, None

    def download_single_file_to_disk(self, namespace: str, pod_name: str, logfile_name: str):
        detail = self.get_pod_detail(namespace, pod_name, pod_name)
        rpm_source = detail.labels[ContainerLabels.tableau_bridge_rpm_source]
        user_as_tableau = bool(detail.labels[ContainerLabels.user_as_tableau])
        logs_path = BridgeContainerLogsPath.get_logs_path(rpm_source, user_as_tableau)

        # logs_path = detail.labels.get(ContainerLabels.tableau_bridge_logs_path)
        # if not logs_path:
        #     raise Exception(f"container does not have label {ContainerLabels.tableau_bridge_logs_path}")
        # logs_path = self.decode_from_k8s_label(logs_path)
        exec_command = ['tar', 'cf', '-', logs_path + "/" + logfile_name]
        resp = stream.stream(self.client.connect_get_namespaced_pod_exec, pod_name, namespace,
                             command=exec_command,
                             stderr=True, stdin=False,
                             stdout=True, tty=False,
                             _preload_content=False)

        tar_output = io.BytesIO()
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                x = resp.read_stdout()
                tar_output.write(x.encode('ascii'))
            if resp.peek_stderr():
                print("STDERR: %s" % resp.read_stderr())
        tar_output.seek(0)
        TempLogsSettings().create_path() #futuredev: maybe use separate path for k8s temp log files
        tmp_tar = TempLogsSettings.temp_bridge_logs_path / f"{logfile_name}.tar"
        with open(tmp_tar, "wb") as f:
            for chunk in tar_output:
                f.write(chunk)
        resp.close()
        tmp_text_file = TempLogsSettings.temp_bridge_logs_path / logfile_name
        FileHelper.extract_single_tar_content_to_text(tmp_tar, tmp_text_file)
        tmp_tar.unlink()
        return str(tmp_text_file)

    @staticmethod
    def encode_for_k8s_label(value: str):
        encoded = StringUtils.encode_string_base64(value)
        return encoded.replace('+', '-').replace('/', '_').replace('=', '')

    @staticmethod
    def decode_from_k8s_label(value_k8s_base64: str):
        value_base64 = value_k8s_base64.replace('-', '+').replace('_', '/')
        padding_needed = (4 - len(value_base64) % 4) % 4
        value_padded = value_k8s_base64 + ('=' * padding_needed)
        return StringUtils.decode_base64_string(value_padded)

    def create_bridge_pod(self, namespace, container_name, image_url, env_vars, labels, image_pull_policy: str = "Always"):
        template_file = Path(__file__).parent / 'templates' / 'k8s_bridge_pod.yaml'
        with open(template_file) as file:
            file_content = file.read()
        container_name = self.normalize_k8s_name(container_name)
        modified_content = file_content.replace('container-name-placeholder', container_name)
        pod_manifest = yaml.safe_load(modified_content)
        pod_manifest['spec']['containers'][0]['image'] = image_url
        ln = pod_manifest['metadata']['labels']
        invalid_chars_regex = re.compile(r'[^a-zA-Z0-9\-_.]')
        for k, v in labels.items():
            sanitized_value = re.sub(invalid_chars_regex, '', v)
            ln[k] = sanitized_value[:63]
        env_list = [{"name": key, "value": value} for key, value in env_vars.items()]
        pod_manifest['spec']['containers'][0]['env'] = env_list
        pod_manifest['spec']['containers'][0]['imagePullPolicy'] = image_pull_policy
        try:
            api_response = self.client.create_namespaced_pod(body=pod_manifest, namespace=namespace)
        except Exception as ex:
            if hasattr(ex, "reason") and  ex.reason == "Conflict":
                return f"pod named `{container_name}` already exists in namespace `{namespace}`"
            raise ex
        return None
        # waiting = True
        # while waiting:
        #     api_response = self.client.read_namespaced_pod(name=container_name, namespace=namespace)
        #     if api_response.status.conditions:
        #         for condition in api_response.status.conditions:
        #             if condition.type == "Ready" and condition.status == "True":
        #                 print(f"Pod {container_name} is ready!")
        #                 waiting = False
        #                 break
        #             elif condition.type == "ContainersReady" and condition.status == "False":
        #                 print(f"Pod {container_name} failed to start. Status: {condition.message}")
        #                 waiting = False
        #                 break
        #     sleep(1)  # Wait for 1 second before checking again
#        return api_response
        # print("Pod created. Status='%s'" % str(api_response.status))

    def get_stdout_pod_logs(self, namespace: str, pod_name: str) -> str:
        logs = self.client.read_namespaced_pod_log(pod_name, namespace, timestamps=True)
        return logs

    def delete_pod(self, namespace, container_name):
        api_response = self.client.delete_namespaced_pod(container_name, namespace)
        return api_response

    def create_namespace(self, k8s_namespace):
        body = client.V1Namespace(metadata=client.V1ObjectMeta(name=k8s_namespace))
        api_response = self.client.create_namespace(body)
        return api_response


@dataclass
class ConnectResult:
    can_connect: bool = False
    error: str = None
