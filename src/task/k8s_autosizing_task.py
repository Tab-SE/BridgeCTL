from datetime import datetime, timedelta
from time import sleep

from src import bridge_settings_file_util
from src.k8s_bridge_manager import K8sBridgeManager
from src.models import AppSettings
from src.task.background_task import BackgroundTask, BG_LOGGER
from src.k8s_client import K8sClient
from src.docker_client import DockerClient
from src.token_loader import TokenLoader


class K8sAutoSizingTask:
    def __init__(self):
        self.bg_task = BackgroundTask(self.run)
        self.run_interval: timedelta = timedelta(hours=.1)
        self.img_tag = None
        self.replica_count: int = 1
        self.last_run = None
        self.last_message = ""
        self.logger = BG_LOGGER
        self.token_loader = TokenLoader(self.logger)

    def set_params(self, app: AppSettings):
        self.run_interval = timedelta(hours=app.autoscale_check_interval_hours)
        self.img_tag = app.autoscale_img_tag
        self.replica_count = app.autoscale_replica_count

    def check_status(self):
        return self.bg_task.check_status()

    def start(self):
        self.logger.info("starting background task to autoscale bridge pods")
        self.last_run = None
        self.last_message = ""
        return self.bg_task.start()

    def stop(self):
        # self.last_message = None
        # self.last_run = None
        return self.bg_task.stop()

    def get_next_token(self):
        tokens = self.token_loader.load_tokens()
        next_available_token = next((t for t in tokens if not t.is_admin_token()), None)
        return next_available_token

    def run(self):
        while not self.bg_task.stop_event.is_set():
            if self.last_run and datetime.now() - self.last_run < self.run_interval:
                sleep(3)
                continue
            self.last_run = datetime.now()
            app = AppSettings.load_static()
            k8s_client = K8sClient()
            pods = k8s_client.get_pod_names_by_prefix(app.k8s_namespace, DockerClient.bridge_prefix)
            bridge_pod_count = len(pods)
            if bridge_pod_count < app.autoscale_replica_count:
                msg = f"bridge pod count {bridge_pod_count} is too low, starting pod. "
                req = bridge_settings_file_util.load_settings()
                mgr = K8sBridgeManager(self.logger, req, app)
                t = self.get_next_token()
                friendly_error = mgr.run_bridge_container_in_k8s(t.name, self.img_tag)
                if friendly_error:
                    msg += f"\nerror starting pod: {friendly_error}"
                else:
                    msg += f"\nPod started"
            elif bridge_pod_count > app.autoscale_replica_count:
                pod_name = pods[0]
                k8s_client.delete_pod(app.k8s_namespace, pod_name)
                msg = f"bridge pod count {bridge_pod_count} is too high, deleted pod {pod_name}"
            else:
                msg = f"bridge pod count {bridge_pod_count} is correct"
            self.last_message = msg
            self.logger.info(msg)

        self.logger.info("Background task has been stopped.")

K8S_TASK = K8sAutoSizingTask()