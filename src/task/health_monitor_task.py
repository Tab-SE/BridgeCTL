import traceback
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from time import sleep

from src import bridge_settings_file_util
from src.bridge_container_runner import BridgeContainerRunner
from src.cli import bridge_status_logic
from src.cli.app_config import APP_NAME, APP_CONFIG
from src.cli.app_logger import AppLogger
from src.docker_client import DockerClient
from src.lib.general_helper import MachineHelper
from src.lib.pagerduty_client import PagerDutyClient
from src.lib.newrelic_client import NewRelicClient
from src.lib.slack_notifier import SlackNotifier
from src.models import AppSettings
from src.task.background_task import BackgroundTask, BG_LOGGER
from src.page.ui_lib.page_util import PageUtil
from src.token_loader import TokenLoader


@dataclass
class AgentReport:
    agent_name: str = None
    pool_name: str = None
    status: str = None

class AgentHealthCategory:
    healthy = "healthy"
    unhealthy = "unhealthy"

class HealthMonitorTask:
    def __init__(self):
        self.bg_task = BackgroundTask(self.check_agents_loop)
        self.last_run = None
        self.last_message = ""
        self.last_message_health = None
        self.run_interval = None

    def check_status(self):
        return self.bg_task.check_status()

    def start(self, monitor_check_interval_hours):
        BG_LOGGER.info("starting background task to monitor bridge agent connection")
        self.last_run = None
        self.change_interval(monitor_check_interval_hours)
        return self.bg_task.start()

    def stop(self):
        return self.bg_task.stop()

    def trigger_run_now(self):
        self.last_run = None
        self.last_message = ""

    def change_interval(self, monitor_check_interval_hours):
        self.run_interval = timedelta(hours=monitor_check_interval_hours)

    def check_agents_loop(self):
        while not self.bg_task.stop_event.is_set():
            sleep(.1)
            if not self.last_run or (datetime.now(timezone.utc) - self.last_run >= self.run_interval):
                self.last_run = datetime.now(timezone.utc)
                self.do_check_agents()
                sleep(3)
        BG_LOGGER.info("Background task check_agents has stopped.")

    def log_msg(self, msg):
        BG_LOGGER.info(msg)
        self.last_message += "\n" + msg

    def do_check_agents(self):
        try:
            # STEP - Init
            app = AppSettings.load_static()
            if not app.monitor_enable_monitoring: #ensure that any background tasks get stopped that are in-flight.
                self.stop()
                BG_LOGGER.warning("monitoring is no longer enabled")
                return
            token = PageUtil.get_admin_pat_or_log_error(BG_LOGGER)
            if not token:
                self.log_msg("No admin token found, unable to monitor bridge agents")
                return
            BG_LOGGER.info(f"checking health of bridge agents")
            agents_status, headers = bridge_status_logic.display_bridge_status(token, BG_LOGGER, True)
            self.last_message = ""
            self.last_message_health = None
            agents_monitored = []
            agents_disconnected = []
            agents_connected = []
            agents_by_pool_count = {}
            monitor_only_pools_display = ', '.join(app.monitor_only_pools) if app.monitor_only_pools else "(all)"

            if app.monitor_only_pools:
                agents_by_pool_count = dict.fromkeys(app.monitor_only_pools, 0)
            for a in agents_status:
                ar = AgentReport(agent_name=a[0], pool_name=a[1], status=a[4])
                if ar.pool_name in agents_by_pool_count:
                    agents_by_pool_count[ar.pool_name] += 1
                ar.pool_name = a[1]
                if app.monitor_only_pools and ar.pool_name not in app.monitor_only_pools:
                    continue
                agents_monitored.append(ar)
                if ar.status != "CONNECTED":
                    agents_disconnected.append(ar)
                else:
                    agents_connected.append(ar)
            # check if any of the values in agents_by_pool_count are 0
            msg_empty_pool = ""
            if app.monitor_only_pools and 0 in agents_by_pool_count.values():
                for pool_name in agents_by_pool_count:
                    if agents_by_pool_count[pool_name] == 0:
                        msg_empty_pool += f" no agents in pool _{pool_name}_."
            if len(agents_disconnected) == 0 and not msg_empty_pool:
                self.last_message_health = AgentHealthCategory.healthy
                mh = f"all monitored agents healthy in pool {monitor_only_pools_display} for site {token.sitename}"
                self.log_msg(mh)
            else:
                self.last_message_health = AgentHealthCategory.unhealthy
                msg = ""
                if msg_empty_pool:
                    msg += f"{APP_NAME} detected empty pool for Tableau Cloud site *{token.sitename}*\n"
                    msg += msg_empty_pool
                if len(agents_disconnected) > 0:
                    msg = "🚦️ *BridgeCTL Alert* 🚦\n"
                    msg += f"{APP_NAME} detected unhealthy Tableau Bridge Agents for Tableau Cloud site *{token.sitename}*    host: {MachineHelper.get_hostname()}\n"
                    msg += f"⚠️ Unhealthy agents: {len(agents_disconnected)} of {len(agents_monitored)} in pool _{monitor_only_pools_display}_\n"
                    for a in agents_disconnected:
                        p = f", pool:{a.pool_name}" if a.pool_name != monitor_only_pools_display else ""
                        msg += f"  - {a.agent_name} {a.status}{p}\n"
                self.log_msg(msg)
                if app.monitor_pager_duty_routing_key:
                    pager_duty_client = PagerDutyClient(app.monitor_pager_duty_routing_key, BG_LOGGER)
                    pager_duty_client.trigger_pagerduty_alert("Tableau Cloud Bridge Agents Disconnected", msg)
                    self.log_msg("PagerDuty alert triggered")
                if app.monitor_slack_api_key:
                    slack_client = SlackNotifier(BG_LOGGER, app.monitor_slack_api_key)
                    if app.monitor_slack_recipient_email:
                        slack_client.send_private_message(app.monitor_slack_recipient_email, msg)
                    if app.monitor_slack_recipient_channel_id:
                        slack_client.send_channel_message(app.monitor_slack_recipient_channel_id, msg)
                    self.log_msg("Slack alert sent")
                else:
                    self.log_msg("Slack api key or email are not set")
                if app.monitor_newrelic_insert_key and app.monitor_newrelic_account_id:
                    newrelic_client = NewRelicClient(BG_LOGGER, app.monitor_newrelic_insert_key, app.monitor_newrelic_account_id)
                    newrelic_client.trigger_newrelic_alert("Tableau Cloud Bridge Agents Disconnected", msg)
                    self.log_msg("New Relic alert sent")
                self.do_auto_healing(agents_connected, app)
            self.last_run = datetime.now(timezone.utc)
        except Exception:
            stack_trace = traceback.format_exc()
            msg = f"Error in check_agents:\n{stack_trace}"
            BG_LOGGER.error(msg)
            self.last_message += msg

    def do_auto_healing(self, agents_connected, app: AppSettings):
        if not app.monitor_auto_heal_enable:
            return
        if not APP_CONFIG.is_internal_build():
            self.log_msg(f"Auto-healing disabled for non-devbuilds")
            return
        if app.monitor_only_pools and len(app.monitor_only_pools) != 1:
            return

        connected_bridge_pod_count = len(agents_connected)
        deficit = app.monitor_auto_heal_min_agents - connected_bridge_pod_count
        if deficit <= 0:
            self.log_msg(f"Connected Bridge agent container count is {connected_bridge_pod_count} for pool {app.monitor_only_pools[0]} ✅, no auto healing needed")
            return
        self.log_msg(f"Expected bridge agent count is {app.monitor_auto_heal_min_agents} and actual is {connected_bridge_pod_count}")

        req = bridge_settings_file_util.load_settings()
        app = AppSettings.load_static()
        token_loader = TokenLoader(BG_LOGGER)
        docker_client = DockerClient(BG_LOGGER)
        existing_container_names = docker_client.get_bridge_container_names()
        available_token_names, in_use_token_names, tokens = token_loader.get_available_tokens(existing_container_names)
        for i in range(deficit):
            if not available_token_names:
                self.log_msg(f"No available Tokens found, unable to add agent container.")
                break
            token_name = available_token_names.pop(0)
            self.log_msg(f"Adding agent container in local docker with token {token_name}")
            token = token_loader.get_token_by_name(token_name)
            runner = BridgeContainerRunner(BG_LOGGER, req, token)
            is_success = runner.run_bridge_container_in_docker(app)
            if is_success:
                BG_LOGGER.info("SUCCESS: Container Started")
            else:
                BG_LOGGER.warning("Container Not Started")
          #= Next Step Logic:
          # - detect if PAT token is bad
          #   = look at stdout for "PAT token invalid"
          #     ++ if yes, remove the container and remove the token from bridge_tokens.yml

    @staticmethod
    def send_test_notification(app: AppSettings, is_slack: bool, is_pager_duty: bool, is_newrelic: bool, test_message, logger: AppLogger) -> (bool, str):
        msg = ""
        is_success = True
        if is_slack:
            slack_client = SlackNotifier(logger, app.monitor_slack_api_key)
            if app.monitor_slack_recipient_channel_id:
                slack_client.send_channel_message(app.monitor_slack_recipient_channel_id, test_message)
            if app.monitor_slack_recipient_email:
                slack_client.send_private_message(app.monitor_slack_recipient_email, test_message)
            msg += "Test notification sent to slack\n\n"
        if is_pager_duty:
            pager_duty_client = PagerDutyClient(app.monitor_pager_duty_routing_key, logger)
            pager_duty_client.trigger_pagerduty_alert("Test Pager Duty Alert", test_message)
            msg += "Test notification sent to Pager Duty\n\n"
        if is_newrelic:
            newrelic_client = NewRelicClient(logger, app.monitor_newrelic_insert_key, app.monitor_newrelic_account_id)
            newrelic_client.trigger_newrelic_alert("Test New Relic Alert", test_message)
            msg += "Test notification sent to New Relic\n\n"
        return is_success, msg



HEALTH_MONITOR_TASK = HealthMonitorTask()