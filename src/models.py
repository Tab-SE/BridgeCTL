import dataclasses
import inspect
import os
import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict

import yaml

from src.enums import DEFAULT_BASE_IMAGE, ADMIN_PAT_PREFIX, DEFAULT_LINUX_DISTRO, DEFAULT_BRIDGE_LOGS_PATH, \
    DEFAULT_DOCKER_NETWORK_MODE, LOG_DIR
from src.lib.general_helper import StringUtils


@dataclass
class BaseClass:
    @classmethod
    def from_dict(cls, data: dict):
        ### Convert dictionary to Python class
        ### if a new property doesn't exist in an existing dictionary loaded from yaml then we should add that property with the default value specified in the class
        kwargs = {k: v for k, v in data.items() if k in inspect.signature(cls).parameters}
        return cls(**kwargs)

    def to_dict(self):
        return dataclasses.asdict(self)


class BridgeRpmSource:
    devbuilds = "devbuilds"
    tableau_com = "tableau.com"


@dataclass
class PatToken:
    name: str
    secret: str
    sitename: str
    pod_url: str = None
    comment: str = None
    site_id: str = None
    site_luid: str = None
    user_email: str = None
    user_domain: str = None
    pool_id: str = None
    pool_name: str = None

    def get_pod_url(self):
        return self.pod_url

    def get_bridge_settings_url(self):
        return f"{self.pod_url}/#/site/{self.sitename}/bridge"

    def is_admin_token(self):
        return self.name.startswith(ADMIN_PAT_PREFIX)

    def to_pat_token_secret(self):
        return PatTokenSecret(name=self.name, secret=self.secret, comment=self.comment)

    @staticmethod
    def get_my_account_settings_url(pod_url, sitename, user_domain, user_email):
        is_valid =  pod_url and sitename and user_domain and user_email
        return f"{pod_url}/#/site/{sitename}/user/{user_domain}/{user_email}/settings", is_valid

    @staticmethod
    def get_my_account_settings_link_markdown(pod_url, sitename, user_domain, user_email):
        lnk, is_valid = PatToken.get_my_account_settings_url(pod_url, sitename, user_domain, user_email)
        if is_valid:
            return f"[My Account Settings]({lnk})"
        else:
            return "My Account Settings"

@dataclass
class PatTokenSecret:
    name: str
    secret: str
    comment: str

    @staticmethod
    def from_dict(x: dict):
        return PatTokenSecret(name=x['name'], secret=x['secret'], comment=x.get('comment'))

@dataclass
class TokenSite:
    """
    Stored in the bridge_tokens.yml
    """
    sitename: str
    pod_url: str
    site_luid: str = None
    site_id: str = None
    user_email: str = None
    user_domain: str = None
    pool_id: str = None
    pool_name: str = None
    edge_manager_id: str = None
    gw_api_token: str = None #maybe rename to edge_api_token

    @staticmethod
    def from_dict(x: dict):
        return TokenSite(sitename=x.get('sitename'), pod_url=x.get('pod_url'), site_id=x.get('site_id'), site_luid=x.get('site_luid'),
                         user_email=x.get('user_email'), user_domain=x.get('user_domain'), pool_id=x.get('pool_id'), pool_name=x.get('pool_name'),
                         edge_manager_id=x.get('edge_manager_id'), gw_api_token=x.get('gw_api_token'))


@dataclass
class BridgeSiteTokens:
    site: TokenSite
    tokens: List[PatTokenSecret]

class TCUrls:
    PROD_USEAST = "https://prod-useast-a.online.tableau.com"
    ALPO_DEV = "https://us-west-2a.online.tableau.com"
    DEV_JUANITA = "https://dev-juanita.online.dev.tabint.net"
    all_urls = [PROD_USEAST, ALPO_DEV, DEV_JUANITA]

    def get_pod_name_from_url(self, url) -> str or None:
        for key, value in self.__class__.__dict__.items():
            if value == url:
                return key
        return None


@dataclass
class BridgeContainerSettings(BaseClass):
    include_drivers: List[str] = None
    base_image: str = None
    linux_distro: str = None
    bridge_rpm_source: str = BridgeRpmSource.tableau_com
    bridge_rpm_version_devbuilds_is_specific: bool = False
    bridge_rpm_version_devbuilds: str = None #devbuilds version.
    bridge_rpm_version_tableau_com: str = None #tableau.com version
    use_minerva_rpm: bool = True
    user_as_tableau: bool = False
    image_name_suffix: str = None
    docker_network_mode: str = DEFAULT_DOCKER_NETWORK_MODE # valid values: 'bridge', 'host', (custom network name) #FutureDev: maybe move to AppSettings
    dns_mappings: Dict[str, str] = None
    unc_path_mappings: Dict[str, str] = None
    db_driver_eula_accepted: bool = False #FutureDev: move to AppSettings
    only_db_drivers: bool = False # only generate Dockerfile with drivers, no bridge rpm. image name prefix: "base_"
    locale: str = None

    def use_minerva(self):
        if self.bridge_rpm_source == BridgeRpmSource.devbuilds:
            return self.use_minerva_rpm
        return str(self.bridge_rpm_version_tableau_com) > "20243" and not self.user_as_tableau

@dataclass
class BridgeRequest(BaseClass):
    bridge: BridgeContainerSettings = None
    def __post_init__(self):
        if isinstance(self.bridge, dict):
            self.bridge = BridgeContainerSettings.from_dict(self.bridge)

def create_new_bridge_container_settings():
    return BridgeContainerSettings(
        base_image= DEFAULT_BASE_IMAGE,
        linux_distro= DEFAULT_LINUX_DISTRO,
        include_drivers= ["postgresql"])


app_settings_path = str(pathlib.Path(__file__).parent.parent / "config" / "app_settings.yml")
DEFAULT_VALID_LOGS_PATH_PREFIX = "~/Documents"

DEFAULT_ECR_REPOSITORY_NAME = "tableau-bridge"
# DEFAULT_ECR_PUBLIC_ALIAS = "l1p6i8f3"

class AppState:
    """
    AppState is a simple class that tracks if the app is loaded for the first time.
    """
    first_app_load: bool = True
    migrated_tokens: bool = False

APP_STATE = AppState()

CURRENT_APP_SETTINGS_SCHEMA_VERSION = 22

@dataclass
class AppSettings:
    """
    AppSettings is a dataclass that stores user application settings in a yaml file.
    """
    schema_version: int = CURRENT_APP_SETTINGS_SCHEMA_VERSION
    valid_log_paths_prefixes: List[str] = dataclasses.field(default_factory=list)
    logs_source_type: str = None
    logs_disk_path: str = None
    logs_disk_file: str = None
    logs_docker_container_name: str = None
    logs_docker_file: str = None
    logs_k8s_pod_name: str = None
    logs_k8s_file: str = None
    devbuilds_username: str = ""
    devbuilds_password: str = ""
    streamlit_server_address: str = "localhost"
    feature_example_scripts_enabled: bool = False
    feature_k8s_enabled: bool = False
    k8s_namespace: str = "tableau"
    img_registry_type: str = None
    aws_region: str = "us-west-2"
    aws_profile: str = None
    selected_image_tag: str = None # local docker image
    selected_remote_image_tag: str = None # remote AWS ECR image
    manage_docker_containers_target_count: int = 1
    feature_aws_ecr_enabled: bool = False
    ecr_private_aws_account_id: str = None
    ecr_private_repository_name: str = None
    azure_acr_enabled: bool = None
    azure_acr_subscription_id: str = None
    azure_acr_resource_group: str = None
    azure_acr_name: str = None
    repository_remote_machine_enabled: bool = False
    repository_remote_machine_address: str = None
    repository_remote_machine_ssh_path: str = None

    dataconnect_feature_enable: bool = False
    dataconnect_registry_secret: str = None
    dataconnect_pool_id: str = None
    dataconnect_registry_ip_address: str = None

    feature_hammerhead_enabled: bool = False

    monitor_slack_api_key: str = None
    monitor_slack_recipient_email: str = None
    monitor_slack_recipient_channel_id: str = ""
    monitor_pager_duty_routing_key: str = None
    monitor_newrelic_insert_key: str = None
    monitor_newrelic_account_id: str = None
    monitor_check_interval_hours: float = .5
    monitor_only_pools: List[str] = None
    monitor_enable_monitoring: bool = False
    monitor_auto_heal_enable: bool = False
    monitor_auto_heal_min_agents: int = 1

    autoscale_replica_count: int = 1
    autoscale_check_interval_hours: float = 1.0 #FutureDev: move to bridge/k8s settings
    autoscale_img_tag: str = None
    autoscale_show_page: bool = False
    feature_enable_edge_network_page: bool = False
    login_password_for_bridgectl: str = None

    feature_jobs_ai_summary: bool = False
    job_timezone_offset: int = 0
    openai_api_key: str = None
    dismiss_initial_feedback_dialog: bool = False

    feature_enable_chat_with_tableau: bool = False
    chat_with_tableau_selected_data_source: str = None

    def __post_init__(self):
        if not self.valid_log_paths_prefixes:
            self.valid_log_paths_prefixes.append(DEFAULT_VALID_LOGS_PATH_PREFIX)

    @staticmethod
    def load_static() -> 'AppSettings':
        app = AppSettings()
        app.load()
        return app

    def load(self, settings_file: str = app_settings_path):
        self._settings_file = settings_file
        if not os.path.exists(self._settings_file):
            return

        with open(self._settings_file, 'r') as infile:
            data = yaml.safe_load(infile)
        if not data:
            return
        is_upgraded = AppSettingsSchemaUpgrade.upgrade_schema(data)

        # Drop unknown properties
        props = set([f.name for f in dataclasses.fields(self)])
        for k in set(data.keys()):
            if k not in props:
                data.pop(k)
        self.__init__(**data)
        if is_upgraded:
            self.save()

    def save(self):
        with open(self._settings_file, 'w') as outfile:
            yaml.dump(dataclasses.asdict(self), outfile, default_flow_style=False, sort_keys=False)
        # Store settings with tokens / passwords in secure way
        os.chmod(self._settings_file, 0o600)

    def is_ecr_configured(self):
        return self.feature_aws_ecr_enabled and self.ecr_private_aws_account_id and self.ecr_private_repository_name

    def is_monitor_autoscale_effective(self):
        return self.monitor_auto_heal_enable and len(self.monitor_only_pools) == 1


class AppSettingsSchemaUpgrade:
    @staticmethod
    def upgrade_schema(data):
        """
        Upgrades the app settings schema to the latest version.
        Returns True if any upgrades were performed, False otherwise.
        """
        if not data:
            return False            
        current_version = data.get("schema_version", 0)
        original_version = current_version
        if current_version == CURRENT_APP_SETTINGS_SCHEMA_VERSION:
            return False
        try:
            if current_version < 21:
                current_version = 21
            # Apply upgrades sequentially
            while current_version < CURRENT_APP_SETTINGS_SCHEMA_VERSION:
                if current_version == 21:
                    data["feature_aws_ecr_enabled"] = data.pop("feature_ecr_enabled", False)
                                
                current_version += 1
                data["schema_version"] = current_version
        except Exception as ex:
            print(f"Error upgrading schema from version {current_version}: {ex}")
        return original_version != current_version

class LoggerInterface(ABC):
    @abstractmethod
    def info(self, msg: str = ""):
        pass

    @abstractmethod
    def warning(self, msg: str):
        pass

    @abstractmethod
    def error(self, msg: str, ex: Exception = None):
        pass


class DiskLogger(LoggerInterface):
    def __init__(self, logger: LoggerInterface, log_file_prefix: str):
        current_datetime = StringUtils.current_datetime_seconds()
        file_name = log_file_prefix + "_" + f"{current_datetime}.log"
        self.log_file = LOG_DIR / file_name
        self.logger = logger
        os.makedirs(LOG_DIR, exist_ok=True)
        current_date_time = datetime.now()
        self.log_to_file("INFO", f"New logger started: {current_date_time}")

    def log_to_file(self, level: str, msg):
        with open(self.log_file, "a") as log_obj:
            print(f"[{level}] {msg}", file=log_obj)

    def info(self, msg: str = ""):
        self.log_to_file("INFO", msg)
        if self.logger:
            self.logger.info(msg)

    def warning(self, msg: str):
        self.log_to_file("WARNING", msg)
        if self.logger:
            self.logger.warning(msg)

    def error(self, msg: str, ex: Exception = None):
        self.log_to_file("ERROR", msg)
        if self.logger:
            self.logger.error(msg, ex)

@dataclass
class LoginUser:
    username: str = None
    password_hash: str = None
    permissions: str = None


@dataclass
class LoginUserHash(LoginUser):
    password_hash: str = None


class ValidationException(Exception):
    pass

CONFIG_DIR = pathlib.Path(__file__).parent.parent / "config"

CONFIG_BACKUP_DIR = CONFIG_DIR / "backup"

class BridgeImageName:
    tableau_bridge_prefix = "tableau_bridge"

    @staticmethod
    def version_from_file_name(rpm_file_name):
        version = rpm_file_name.replace(".x86_64.rpm", "") if rpm_file_name else ""
        return version.replace("tableau-bridge-", "").replace("TableauBridge-", "")

    @classmethod
    def local_image_name(cls, req: BridgeRequest):
        linux_distro = req.bridge.linux_distro.lower() if req.bridge.linux_distro else "linux"
        if req.bridge.only_db_drivers:
            prefix = "base"
            rpm_version = ""
        else:
            prefix = cls.tableau_bridge_prefix
            v = req.bridge.bridge_rpm_version_devbuilds if req.bridge.bridge_rpm_source == BridgeRpmSource.devbuilds else req.bridge.bridge_rpm_version_tableau_com
            rpm_version = f"_{v}" if v else "_version_unknown"
        suf = "_" + req.bridge.image_name_suffix if req.bridge.image_name_suffix else ""
        image_name = f"{prefix}_{linux_distro}{rpm_version}{suf}"
        return image_name
