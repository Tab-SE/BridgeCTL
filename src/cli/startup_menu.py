import os
import pathlib
import shutil
import sys
import time
import traceback
from enum import Enum

import questionary

import src.cli
import src.cli.show_ascii
import src.os_type
import src.token_loader
from src import bridge_settings_file_util
from src.cli import show_ascii, platform_helper
from src.cli.app_config import APP_CONFIG
from src.cli.app_logger import LOGGER
from src.cli.edit_app_settings import save_streamlit_url_in_config, streamlit_toml_file
from src.cli.help_menu import HelpMenuQuestion
from src.cli.question_model import Question
from src.cli.questionary_helper import extended_choice
from src.lib.pslib import PsLib
from src.models import AppSettings
from src.os_type import OsType
from src.os_type import current_os
from src.subprocess_util import SubProcess


class ContainerMenuExitCode(Enum):
    NONE = 0
    KILLED = 1

def print_welcome_message(show_logo: bool):
    if show_logo:
        LOGGER.info_rich(show_ascii.LOGOS[0], style="green bold", highlight=False)
    LOGGER.info_rich("Bridge CTL - A command-line utility to build, run, and monitor Tableau Bridge Agents in containers", style="green", highlight=False)
    gh = "" if APP_CONFIG.is_internal_build() else "github.com/"
    LOGGER.info(f"Downloaded from {gh}{APP_CONFIG.target_github_repo}")


def get_streamlit_server_address_from_config() -> (str, str):
    config_file = os.path.join(pathlib.Path(__file__).parent.parent.parent / ".streamlit" / "config.toml")
    address = "localhost"
    port = "8505"
    if not os.path.exists(config_file):
        return address, port

    with open(config_file) as f:
        for line in f:
            if line.startswith("address"):
                address = line.split("=")[1].strip().strip('"')
            elif line.startswith("port"):
                port = line.split("=")[1].strip()

    return address, port

def init_streamlit_credentials():
    streamlit_dir = os.path.expanduser("~/.streamlit")
    if not os.path.exists(streamlit_dir):
        os.mkdir(streamlit_dir)
    credentials_file = os.path.join(streamlit_dir, "credentials.toml")
    if not os.path.exists(credentials_file):
        with open(credentials_file, "w") as f:
            f.write("[general]\nemail = \"\"\n")

def copy_streamlit_config_from_template():
    template = streamlit_toml_file.parent / "config_template.toml"
    if not os.path.exists(streamlit_toml_file):
        LOGGER.info(f"copying {template} to {streamlit_toml_file}")
        shutil.copyfile(template, streamlit_toml_file)

def stop_streamlit():
    PsLib.stop_streamlit()

def quit_cli():
    # stop_streamlit()
    print("Quiting cli")
    sys.exit(0)

def run_streamlit():
    LOGGER.info("Starting BridgeCTL User Interface")
    # STEP - Prevent streamlit from prompting for email
    init_streamlit_credentials()
    copy_streamlit_config_from_template()

    # STEP - Sync streamlit server address from config.app_settings.yml to .streamlit/config.toml
    app_settings = AppSettings()
    app_settings.load()
    address, port = get_streamlit_server_address_from_config()
    if app_settings.streamlit_server_address and (address != app_settings.streamlit_server_address):
        save_streamlit_url_in_config(app_settings.streamlit_server_address)
        address = app_settings.streamlit_server_address

    url = f"http://{address}:{port}"

    # STEP - Check if already running
    script_name = "streamlit run Home.py"
    proc_pid = PsLib.find_process_id_by_name(script_name)
    if proc_pid:
        LOGGER.info(f"  UI is already running")
        LOGGER.info(f"opening {url}\n")
        if current_os() != OsType.linux:
            platform_helper.open_webbrowser_util(url)
        return

    cmd = f'"{sys.executable}" -m {script_name}'
    LOGGER.info(f"Executing command: {cmd}")

    LOGGER.info(f"url: {url}")
    working_dir = pathlib.Path(__file__).parent.parent.parent

    # Dynamically wait N seconds for server to start
    sleep_duration = 5
    try:
        process = SubProcess.run_popen(cmd, working_dir)
        for _ in range(sleep_duration):
            if process.poll() is None:
                print(".", end="", flush=True)
                time.sleep(1)
            else:
                break
        print("")
        if process.poll() is None: # if it is still running after 5 seconds then we assume success
            LOGGER.info(f"Successfully started UI")
        else:
            LOGGER.error(f"Error starting UI. Process exited with code {process.poll()}")
            LOGGER.error(f"{process.stderr.read()}")

    except Exception as e:
        LOGGER.error(f"Failed to start Streamlit UI: {e}")


class StartMenuQuestion(Question):
    m_run_streamlit_menu = "Start UI"
    m_stop_streamlit_menu = "Stop UI"
    m_open_browser_bridge_admin = "Tableau Cloud Browse Bridge Settings"
    m_edit_app_settings = "Edit UI Service Settings"
    m_show_help = "Help ->"
    m_quit = "Quit"

    MENU_SELECTION = "MENU "

    def ask(self):
        try:
            config = bridge_settings_file_util.load_settings()
        except Exception as ex:  # note, we want to catch any errors loading config settings on startup to enable update
            LOGGER.error(f"error while opening config file: {traceback.print_exc()}")

        choices = [
            extended_choice(title=self.m_run_streamlit_menu),
            extended_choice(title=self.m_stop_streamlit_menu),
            extended_choice(title=self.m_edit_app_settings),
            extended_choice(title=self.m_show_help),
            extended_choice(title=self.m_quit)
        ]

        # Remove disabled menu items
        choices = [x for x in choices if x is not None]

        try:
            self.answer = questionary.select("Main Menu", choices, style=src.cli.show_ascii.custom_style).unsafe_ask()
        except KeyboardInterrupt:
            return self.root_app.signal_handler_ask_to_exit(None, None)

        LOGGER.info_file_only(self.MENU_SELECTION + self.answer)
        return self.answer

    def display(self):
        while not self.answer:
            self.asking()

        help_menu = HelpMenuQuestion(root_app=self.root_app)
        try:
            {
                self.m_run_streamlit_menu: run_streamlit,
                self.m_stop_streamlit_menu: stop_streamlit,
                self.m_edit_app_settings: edit_app_settings,
                self.m_show_help: help_menu.display,
                self.m_quit: quit_cli,
            }[self.answer]()
        except Exception as ex:
            LOGGER.error(f"error in menu selection '{self.answer}'", ex)
        self.answer = ""


def edit_app_settings():
    from src.cli.edit_app_settings import EditAppSettings
    EditAppSettings(root_app=None).display()
