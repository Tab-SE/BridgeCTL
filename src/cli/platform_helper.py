import subprocess
import sys
import webbrowser

from src.cli.app_config import APP_NAME
from src.cli.app_logger import LOGGER
from src.enums import LOG_DIR
from src.models import CONFIG_DIR
from src.os_type import current_os, OsType
from src.subprocess_util import SubProcess


def not_supported_os():
    LOGGER.info(f"INVALID: local operating system '{current_os()}' not supported")


def open_webbrowser_util(url):
    if current_os() == OsType.mac:
        webbrowser.open(url)
    elif current_os() == OsType.win:
        webbrowser.open(url)
    else:
        not_supported_os()

def view_app_logs():
    LOGGER.info(f"reveal {APP_NAME} logs in finder\n path: {CONFIG_DIR}")
    if current_os() == OsType.mac:
        subprocess.run(['open', '-R', f'{CONFIG_DIR}'], check=True)
    elif current_os() == OsType.win:
        webbrowser.open(CONFIG_DIR)
    else:
        not_supported_os()
    #FutureDev: remove listing of pip modules.
    # LOGGER.info("List of pip modules installed: ")
    # cmds = [f'{sys.executable} -m pip list']
    # SubProcess(LOGGER).run_cmd(cmds, display_output=True)

def open_log_folder():
    if current_os() == OsType.mac:
        subprocess.run(['open', '-R', f'{LOG_DIR}'], check=True)
    elif current_os() == OsType.win:
        webbrowser.open(LOG_DIR)
    else:
        not_supported_os()


