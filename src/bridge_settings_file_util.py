import dataclasses
from datetime import datetime
import os
import shutil

import questionary
import yaml
from colorama import Fore

from src import models
from src.cli.app_logger import LOGGER
from src.models import CONFIG_DIR, CONFIG_BACKUP_DIR

if not os.path.exists(CONFIG_DIR):
    try:
        os.mkdir(CONFIG_DIR)
    except Exception as e:
        print(Fore.RED + f"Can't create {CONFIG_DIR}/ for config - {e}")

bridge_settings_file_full_path = str(CONFIG_DIR / "bridge_settings.yml")


def save_settings(config: models.BridgeRequest):
    data_dict = dataclasses.asdict(config)
    with open(bridge_settings_file_full_path, 'w') as outfile:
        yaml.dump(data_dict, outfile, default_flow_style=False, sort_keys=False)


def load_settings_as_string() -> str:
    if os.path.exists(bridge_settings_file_full_path):
        with open(bridge_settings_file_full_path, 'r') as f:
            content = f.read()
        return content


def load_settings() -> models.BridgeRequest:
    if not os.path.exists(bridge_settings_file_full_path):
        create_new_settings()
    try:
        with open(bridge_settings_file_full_path, 'r') as f:
            content = yaml.load(f, Loader=yaml.FullLoader)
        config = models.BridgeRequest.from_dict(content)
        # If there were some changes within the config, overwrite with correct schema, but backup first
        if content != dataclasses.asdict(config):
            time_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup = f"settings_backup_{time_stamp}.yml"
            if not os.path.exists(CONFIG_BACKUP_DIR):
                os.makedirs(CONFIG_BACKUP_DIR)
            shutil.copy(bridge_settings_file_full_path, str(CONFIG_BACKUP_DIR / backup))
            save_settings(config)
            LOGGER.info(f"settings.yml schema was updated and the previous bridge_settings.yml was backed up.", None, True)
    except Exception as ex:
        LOGGER.error(f"Error parsing {bridge_settings_file_full_path}", ex=ex)
        exit(1)
    return config


def save_and_reload(config: models.BridgeRequest) -> models.BridgeRequest:
    save_settings(config)
    return load_settings()


# def select_user_email(config: models.BridgeRequest):
#     print("User Email has not been selected")
#     config.bridge.user_email = questionary.text("User Email").ask()
#     save_settings(config)


def create_new_settings():
    LOGGER.info("App settings not found. Creating new ...")
    dcu_req = models.BridgeRequest()
    dcu_req.bridge = models.create_new_bridge_container_settings()
    save_settings(dcu_req)
    LOGGER.info(f"created new config at {bridge_settings_file_full_path}")
