from pathlib import Path


class ImageRegistryType:
    local_docker = "Local Docker"
    aws_ecr = "AWS ECR"
    azure_acr = "Azure ACR"

BRIDGE_CONTAINER_PREFIX = 'bridge_'

DEFAULT_BASE_IMAGE = "registry.access.redhat.com/ubi9/ubi:latest" #futuredev: move to ContainerRepoURIs

class ContainerRepoURI:
    redhat_ubi9_DEFAULT = "registry.access.redhat.com/ubi8/ubi:latest"
    redhat_ubi8_DEFAULT = "registry.access.redhat.com/ubi9/ubi:latest"
    # amazonlinux2023 = "public.ecr.aws/amazonlinux/amazonlinux:2023"
    #ubuntu22 = "docker.io/library/ubuntu:22.04"

DEFAULT_LINUX_DISTRO = "rhel9"

LINUX_DISTROS = ["rhel9", "rhel8"]  #"amazonlinux2023"] # , "ubuntu22",

ADMIN_PAT_PREFIX = "admin-pat"

DEFAULT_BRIDGE_LOGS_PATH = "~/Documents/My Tableau Bridge Repository/Logs"

AMD64_PLATFORM = 'linux/amd64'

VALID_DOCKER_NETWORK_MODES = ["bridge", "host"]
DEFAULT_DOCKER_NETWORK_MODE = "bridge"
DEFAULT_POOL = "(default pool)"

SCRATCH_DIR =  Path(__file__).parent.parent / 'scratch'
LOG_DIR = Path(__file__).parent.parent / "log"
TEMPLATE_DIR = Path(__file__).parent / 'templates'

LOCALHOST = "localhost"

class PropNames:
    host_mount_path = "host_mount_path"
    container_mount_path = "container_mount_path"

class RunContainerAsUser:
    root = "root"
    tableau = "tableau"

locale_list = ["", "en_US"] #, "fr_FR", "de_DE", "es_ES", "ja_JP", "ko_KR", "pt_BR", "zh_CN", "zh_TW"]


class BridgeContainerName:
    @staticmethod
    def get_name(sitename, token_name) -> str:
        if not sitename:
            raise ValueError("site_name is empty")
        if not token_name:
            raise ValueError("token name is empty")
        return f"{BRIDGE_CONTAINER_PREFIX}{sitename}_{token_name}"

    @staticmethod
    def get_token_name(container_name: str, sitename: str) -> str:
        ### Calculate token name from bridge container name
        if not container_name:
            raise ValueError("container_name is empty")
        return container_name.replace(BRIDGE_CONTAINER_PREFIX + f"{sitename}_", "")
