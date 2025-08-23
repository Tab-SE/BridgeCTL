import os
import pathlib
import sys
from platform import python_version

import questionary

import src.cli
import src.cli.show_ascii
from src.cli import app_config, platform_helper, version_check
from src.cli.app_config import APP_CONFIG, APP_NAME, APP_NAME_FOLDER
from src.cli.app_logger import LOGGER
from src.cli.question_model import Question
from src.cli.questionary_helper import extended_choice
from src.cli.uninstall import remove_alias_on_unix, remove_bridgectl_folder
from src.github_version_checker import GithubVersionChecker
from src.os_type import OsType, current_os


class HelpMenuQuestion(Question):
    m_main_menu = "<- Main Menu"
    m_browse_config_dir = "Browse the BridgeCTL Config Directory"
    m_uninstall = "Uninstall BridgeCTL ..."
    m_check_updates = "Check for updates"
    show_welcome: bool

    MENU_SELECTION = "MENU "

    def __init__(self, **kwargs):
        Question.__init__(self, **kwargs)
        self.show_welcome = True

    def ask(self):
        if self.show_welcome:
            LOGGER.info_rich(f"[green]{APP_NAME} version [blue]{APP_CONFIG.app_version}[/blue]")
            LOGGER.info_rich(f"Help Documentation: {APP_CONFIG.readme_url()}",style="green", highlight=False)
            LOGGER.info_rich(f"Current directory: {os.getcwd()}", style="green", highlight=False)
            LOGGER.info_rich(f"Python: {python_version()} at {sys.executable}", style="green", highlight=False)
            LOGGER.info_rich(f"Downloaded from: {GithubVersionChecker().get_releases_home()}, Deployment Tag: {APP_CONFIG.deployment_environment}",style="green", highlight=False)
        try:
            choices = [
                    extended_choice(title=self.m_main_menu, shortcut_key="m"),
                    None if current_os() == OsType.linux else extended_choice(self.m_browse_config_dir),
                    extended_choice(title=self.m_check_updates, shortcut_key="u"),
                    extended_choice(self.m_uninstall),
                ]
            choices = [x for x in choices if x is not None]

            self.answer = questionary.select(
                "Help Menu",
                choices=choices,
                style=src.cli.show_ascii.custom_style).unsafe_ask()
        except KeyboardInterrupt:
            return self.root_app.signal_handler_ask_to_exit(None, None)

        LOGGER.info_file_only(self.MENU_SELECTION + self.answer)
        return self.answer

    def display(self):
        do_ask = True
        while do_ask:
            while not self.answer:
                self.asking()
            try:
                {
                    self.m_main_menu: lambda: ...,
                    self.m_browse_config_dir: platform_helper.view_app_logs,
                    self.m_uninstall: handle_uninstall,
                    self.m_check_updates: check_and_update,
                }[self.answer]()
            except Exception as ex:
                LOGGER.error(f"error in menu selection '{self.answer}'", ex)
            if self.answer != self.m_main_menu:
                print('\n')
                self.show_welcome = False
                self.answer = ""
            else:
                do_ask = False


def show_uninstall_instructions():
    LOGGER.info()
    LOGGER.info(f"Steps to uninstall {app_config.APP_NAME}:")
    cli_dir = pathlib.Path(__file__).parent.parent.parent
    LOGGER.info(f"1) Delete the {APP_NAME_FOLDER} folder at {cli_dir} ")
    if current_os() == src.os_type.OsType.linux:
        LOGGER.info(f"2) Remove {APP_NAME} entries from .bashrc")
    elif current_os() == src.os_type.OsType.mac:
        LOGGER.info(f"2) Remove {APP_NAME} entries from .zshrc")
    elif current_os() == src.os_type.OsType.win:
        LOGGER.info(f"2) Remove {APP_NAME} entries from your PATH")
    # LOGGER.info(f"For more details, see {APP_NAME} documentation: { APP_CONFIG.documentation_url() }")
    LOGGER.info("")

def handle_uninstall():
    show_uninstall_instructions()
    answer = questionary.select(f'Would you like to automatically uninstall {APP_NAME}?',
                                choices=["no", "yes"], style=src.cli.show_ascii.custom_style).ask()
    if answer == "yes":
        print("Uninstalling")
        if os.path.basename(os.getcwd()) != APP_NAME_FOLDER:
            print(f"Error: Current directory is not '{APP_NAME_FOLDER}', unable to remove")
            return
        if os.path.exists(f"{os.getcwd()}{os.path.sep}.git"):
            print("  error: uninstall not supported in source directory (.git directory found)")
            exit(1)

        if current_os() == OsType.linux or current_os() == OsType.mac:
            remove_alias_on_unix()
        elif current_os() == OsType.win:
            print("auto uninstall not yet supported on windows")
            return
        remove_bridgectl_folder()
    else:
        pass


def check_and_update():
    check_version()
    version_check.update_if_new()


def check_version():
    vmsg, latest_ver = version_check.check_latest_and_get_version_message()
    version_msg = f"version {APP_CONFIG.app_version} {vmsg}"
    LOGGER.info_rich(f"{app_config.APP_NAME} {version_msg}")
    LOGGER.usage_log(f"version:{APP_CONFIG.app_version}")
    return vmsg, latest_ver
