import requests

from src.cli.app_config import APP_CONFIG
from src.cli.app_logger import LOGGER
from src.lib.general_helper import MachineHelper, StringUtils


class UsageMetric:
    home_open = "home"
    web_load = "web_load"
    web_show_bridge_scripts = "web_show_bridge_scripts"
    web_show_db_scripts = "web_show_db_scripts"

    settings_chk_updates = "settings_chk_updates"
    cli_start = "cli_start"
    build_bridge_image = "build_bridge_image"
    run_bridge_docker_container = "run_bridge_docker_container"
    hammerhead_report = "hh_report"
    hammerhead_create = "hh_create"
    hammerhead_modify = "hh_modify"
    logs_select_file = "logs_sel_file"
    example_scripts_show = "example_scripts_show"

class UsageLog:
    def __init__(self):
        self.metrics_url = "http://bridgectl.tableautest.com/metrics.yml"
        try:
            if APP_CONFIG.is_internal_build():
                self.hostname = MachineHelper.get_hostname()
            else:
                self.hostname = "blank"
            # self.hostname_h = StringUtils.hash_string(self.hostname)
        except Exception as ex:
            LOGGER.warning(f"Error getting hostname: {ex}")
            self.hostname = "unknown"
            # self.hostname_h = "unknown"

    def log_usage(self, usage_metric: str, usage_param: str = None):
        if not APP_CONFIG.is_internal_build():
            return
        try:
            # hs = self.hostname_h[0:14]
            params = { 'm': usage_metric, 'c': self.hostname}
            if usage_param:
                params['p'] = usage_param
            msg_log = 'logging usage: ' + "&".join(f"{k}={v}" for k, v in params.items())
            LOGGER.info(msg_log)
            response = requests.get(self.metrics_url, params=params)
            if response.status_code != 200:
                LOGGER.warning(f"error logging usage: response status_code: {response.status_code}")
        except requests.exceptions.RequestException as ex:
            LOGGER.warning(f"Network error during usage logging: {ex}")
        except Exception as ex:
            LOGGER.warning(f"Unexpected error logging usage: {ex}")

USAGE_LOG = UsageLog()
