import os
import pathlib
import subprocess
import sys
from typing import Tuple
from packaging import version

import src.cli.show_ascii
from src.cli.app_config import APP_CONFIG, APP_NAME
from src.cli.app_logger import LOGGER
from src.lib.pslib import PsLib
from src.github_version_checker import GithubVersionChecker


def check_python_requirements():
    required_version = '3.10.3'
    current_version = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    if version.parse(current_version) < version.parse(required_version):
        error_message = f"error: python version {required_version} or higher is required. Please upgrade at https://www.python.org/downloads"
        print(error_message)
        exit(1)


new_version_available = False

def check_latest_and_get_version_message():
    try:
        able_to_check, latest_version = check_latest_version()
        latest_version_msg = latest_version
        if not able_to_check:
            latest_version_msg = f"[red]unable to check latest version: {latest_version}[/red]"
        elif version.parse(latest_version) > version.parse(APP_CONFIG.app_version):
            latest_version_msg = f"[green](out-of-date) a new version available:[/green] [blue]{latest_version}[blue]"
            global new_version_available
            new_version_available = True
        elif version.parse(latest_version) == version.parse(APP_CONFIG.app_version):
            latest_version_msg = f"is up-to-date"
        elif version.parse(latest_version) < version.parse(APP_CONFIG.app_version):
            latest_version_msg = f"(pre-release)"
        return f"{latest_version_msg}\n", latest_version
    except Exception as ex:
        msg = "unable to check latest version"
        LOGGER.error(ex)
        # return f"{msg}. {ex}\n"
        return f"{msg}.\n"


def check_latest_version() -> Tuple[bool, str]:
    """
    Check for latest released version of App
    return False if unable to get version
    also return message containing version or reason for failure
    """
    try:
        latest_version = GithubVersionChecker().get_latest_app_version()
        return bool(latest_version), latest_version if latest_version else "'bridgectl_version' not found"
    except Exception as e:
        return False, f"error checking version {e}"
        #return False, f"error checking version {str(e)[0:10]}"


def update_if_new(just_do_it = False) -> bool:
    if not new_version_available:
        return False

    git_folder = f"{str(pathlib.Path(__file__).parent.parent.parent)}/.git"
    if os.path.exists(git_folder):
        LOGGER.info(f"cannot update {APP_NAME} source code directory")
        return False

    LOGGER.info(f"current directory: {os.getcwd()}\n")
    if just_do_it:
        answer = "yes"
    else:
        import questionary
        answer = questionary.select(
            f"A newer version of {APP_NAME} detected, would you like to upgrade?",
            choices=["yes", "cancel"], style=src.cli.show_ascii.custom_style).ask()
    if answer == "yes":
        try:
            PsLib.stop_streamlit()
            setup_url = GithubVersionChecker().get_setup_url()
            LOGGER.info(f"Download latest bridgectl_setup.py from {setup_url}")
            local_filename = str(pathlib.Path(__file__).parent.parent.parent / "bridgectl_setup.py")
            GithubVersionChecker.download_file(setup_url, local_filename)
            LOGGER.info(f"running 'bridgectl_setup.py' in current directory: {os.getcwd()}")
            subprocess.Popen([sys.executable, "bridgectl_setup.py", "update"])
            sys.exit()
        except Exception as ex:
            LOGGER.error(f"error while updating {APP_NAME}", ex=ex)
        return True
