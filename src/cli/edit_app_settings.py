import fileinput
import os
import pathlib
import re
import socket
import sys

import questionary

import src.cli
import src.cli.show_ascii
import src.os_type
from src.cli.app_logger import LOGGER
from src.cli.question_model import Question
from src.lib.general_helper import MachineHelper
from src.models import AppSettings


class EditAppSettings(Question):
    m_main_menu = "<- Main Menu"
    m_edit_streamlit_server_address = "Edit User Interface address"
    m_configure_systemctl_service = "Instructions for running BridgeCTL as a service"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def ask(self):
        try:
            self.answer = questionary.select(
                "Choose action:",
                choices=[
                    self.m_edit_streamlit_server_address,
                    self.m_configure_systemctl_service,
                    self.m_main_menu,
                ],
                style=src.cli.show_ascii.custom_style).unsafe_ask()
        except KeyboardInterrupt:
            return self.root_app.signal_handler_ask_to_exit(None, None)

        return self.answer

    def display(self):
        while True:
            if not self.answer:
                self.asking()
            try:
                {
                    self.m_main_menu: lambda: ...,
                    self.m_edit_streamlit_server_address: edit_streamlit_server_address,
                    self.m_configure_systemctl_service: configure_systemctl_service,
                }[self.answer]()
            except Exception as ex:
                LOGGER.error(f"error in menu selection '{self.answer}'", ex)
            if self.answer == self.m_main_menu:
                break
            else:
                print()
                self.answer = ""

streamlit_toml_file = pathlib.Path(__file__).parent.parent.parent / ".streamlit" / "config.toml"

def save_streamlit_url_in_config(server_address: str):
    # note, as from python 3.11 tomllib will be part of python libraries https://docs.python.org/3/library/tomllib.html

    if not os.path.exists(streamlit_toml_file):
        LOGGER.warning(f"config file '{streamlit_toml_file}' not found, unable to set streamlit server address to {server_address}")
        return

    with streamlit_toml_file.open("r+") as f:
        lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("address"):
                new = f'address = "{server_address}"\n'
                if lines[i] == new:
                    return
                lines[i] = new
                found = True
                break

        if not found:
            LOGGER.info(f"address not found in '{streamlit_toml_file}'")
            return
        # Write the modified lines back to the file
        LOGGER.info(f"saving streamlit server address to '{server_address}' in .streamlit/config.toml")
        f.seek(0)
        f.writelines(lines)
        f.truncate()


def edit_streamlit_server_address():
    app_settings = AppSettings.load_static()

    regex = r'.+'
    edit = True
    server_address = app_settings.streamlit_server_address if app_settings.streamlit_server_address else "localhost"
    hostname = MachineHelper.get_hostname(True)
    LOGGER.info_rich(f"Enter the address for the BridgeCTL Web User Interface. For local-only access set it to 'localhost'. For external access set it to the hostname '{hostname}' or just '0.0.0.0'")
    while edit:
        server_address = questionary.text(
            message="Streamlit server address",
            validate=lambda x: bool(re.fullmatch(regex, x)) or "server address is invalid",
            default=server_address,
            style=src.cli.show_ascii.custom_style
        ).ask()

        answer = questionary.select(f'Save to app_settings.yml?',
                                    choices=["Save", "Cancel"], style=src.cli.show_ascii.custom_style).ask()
        if answer == "Cancel":
            return
        elif answer == "Save":
            edit = False

        if server_address != app_settings.streamlit_server_address:
            app_settings.streamlit_server_address = server_address
            app_settings.save()
            save_streamlit_url_in_config(server_address)
            LOGGER.info(f"Streamlit server address updated to '{server_address}'")


def create_systemd_service():
    bridgectl_dir = str(pathlib.Path(__file__).parent.parent.parent)
    script_name = "streamlit run Home.py"
    start_streamlit_cmd = f'"{sys.executable}" -m {script_name}'
    current_username = os.getlogin()
    script = [
        f'sudo cat <<EOF > /etc/systemd/system/bridgectl.service',
        '[Unit]',
        'Description=BridgeCTL Service',
        'After=network-online.target',
        'Wants=network-online.target',
        '',
        '[Service]',
        'Type=simple',
        f'User={current_username}',
        f'WorkingDirectory={bridgectl_dir}',
        f'ExecStart={start_streamlit_cmd}',
        'Restart=on-failure',
        'RestartSec=10',
        '',
        '[Install]',
        'WantedBy=multi-user.target',
        '',
        'EOF',
        '',
        '',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable bridgectl',
        'sudo systemctl start bridgectl'
    ]
    print("=============================")
    print()
    print('\n'.join(script))
    print()
    print()
    print("============================")


def configure_systemctl_service():
    LOGGER.info("Copy and run the following command to configure a Linux systemd service to run the BridgeCTL UI on system startup")
    LOGGER.info("Note: please check that these variables are correct: 1) User 2) WorkingDirectory and 3) ExecStart")
    LOGGER.info("Note: you need to have sudo permissions to run this command")
    LOGGER.info("Note: Also, set the UI server address to the hostname or ""0.0.0.0"" instead of localhost so it can be accessed externally.")
    create_systemd_service()
