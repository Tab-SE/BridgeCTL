import traceback
from datetime import datetime, timedelta, timezone
from time import sleep

from src.gw_client.dc_gw_client import DcGwClient
from src.gw_client.dc_gw_client_models import GwActions, RemoteCommand
from src.gw_client.dc_gw_config import REMOTE_COMMAND_INTERVAL_SECONDS
from src.gw_client.remote_commands_logic import RemoteCommandLogic
from src.models import TokenSite
from src.task.background_task import BackgroundTask, BG_LOGGER


REMOTE_COMMANDS_TO_PROCESS = {
    "add_bridge_agent": lambda *args: None, # Replace with actual function call
    "remove_bridge_agent": lambda *args: None,
    "upgrade_bridge_agent": lambda *args: None,
    "modify_bridge_client_settings": lambda *args: None
}

class RemoteCommands:
    def __init__(self):
        self.bg_task = BackgroundTask(self.check_commands_loop)
        self.run_interval = None
        self.last_run = None
        self.last_message = None
        self.last_message_health = None
        self.api_gw_token = None

    def change_settings(self, ts: TokenSite):
        self.run_interval = timedelta(seconds=REMOTE_COMMAND_INTERVAL_SECONDS)
        self.api_gw_token = ts.gw_api_token

    def check_status(self):
        return self.bg_task.check_status()

    def start(self): #FutureDev: add app: AppSettings as parameter, and call self.change_settings(app)
        BG_LOGGER.info("starting background task to for remote commands execution")
        self.last_run = None
        return self.bg_task.start()

    def stop(self):
        return self.bg_task.stop()

    def run_now(self):
        self.last_run = None
        self.last_message = None

    def check_commands_loop(self):
        while not self.bg_task.stop_event.is_set():
            sleep(.1)
            if not self.last_run or (datetime.now(timezone.utc) - self.last_run >= self.run_interval):
                self.last_run = datetime.now(timezone.utc)
                self.do_check_commands()
                sleep(3)
        BG_LOGGER.info("Background task check_commands has stopped.")

    def log_msg(self, msg):
        BG_LOGGER.info(msg)
        self.last_message += "\n" + msg

    def do_check_commands(self):
        try:
            self.last_message = ""
            self.last_message_health = None
            gw = DcGwClient(self.api_gw_token)
            ret_commands = gw.get_commands()
            logic = RemoteCommandLogic(BG_LOGGER)
            for command in ret_commands:
                command: RemoteCommand = command
                logic.route_command(command)

            self.last_run = datetime.now(timezone.utc)
        except Exception as ex:
            stack_trace = traceback.format_exc()
            msg = f"Error in check_commands:\n{stack_trace}"
            BG_LOGGER.error(msg)
            self.last_message += msg


REMOTE_COMMANDS: RemoteCommands = RemoteCommands()
