import sys
import traceback

import questionary

import src.cli.show_ascii
from src import models, bridge_settings_file_util
from src.cli import version_check, startup_menu, help_menu
from src.cli.app_config import APP_CONFIG, DeployEnviron
from src.cli.app_logger import LOGGER
from src.cli import batch


class AppClass(object):

    def signal_handler_ask_to_exit(self, sig, frame):
        answer = questionary.select(f'You pressed CTRL+C, would you like to exit?',
                                    choices=["no", "yes"], style=src.cli.show_ascii.custom_style).ask()
        if answer == "yes":
            self.quit()
        return None

    def run(self):
        # STEP - process commandline args
        if len(sys.argv) > 1:
            batch.process_args()
            sys.exit(0)

        # STEP - check for updates
        startup_menu.print_welcome_message(True)
        if APP_CONFIG.deployment_environment != DeployEnviron.stable:
            help_menu.check_version()
        version_check.update_if_new()

        try:
            config = bridge_settings_file_util.load_settings()
            # self.fill_in_config(config)
        except Exception as ex:
            LOGGER.error(f"error while opening config file: {traceback.print_exc()}")
            sys.exit(1)

        # Initialize menu
        start_menu_obj = startup_menu.StartMenuQuestion(root_app=self)
        while True:
            start_menu_obj.display()

    # def fill_in_config(self, config: models.BridgeRequest):
    #     if not config.bridge.user_email:
    #         bridge_settings_file_util.select_user_email(config)

    def quit(self):
        print("Quiting cli")
        sys.exit(0)
