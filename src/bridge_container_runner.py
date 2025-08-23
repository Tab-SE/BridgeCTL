from src import models
from src.bridge_container_builder import BridgeContainerBuilder
from src.cli.bridge_status_logic import BridgeStatusLogic, get_or_fetch_site_id
from src.docker_client import DockerClient, ContainerLabels
from src.ecr_registry_private import EcrRegistryPrivate
from src.enums import ImageRegistryType, RunContainerAsUser, VALID_DOCKER_NETWORK_MODES, \
    DEFAULT_DOCKER_NETWORK_MODE, PropNames, DEFAULT_POOL, BridgeContainerName
from src.lib.tc_api_client import TableauCloudLogin, TCApiClient
from src.models import LoggerInterface, AppSettings
from src.token_loader import TokenLoader


class BridgeContainerRunner:
    def __init__(self, logger: LoggerInterface, req: models.BridgeRequest, token: models.PatToken):
        self.logger: LoggerInterface = logger
        self.req: models.BridgeRequest = req
        self.token: models.PatToken = token
        self.docker_client = DockerClient(self.logger)

    def run_bridge_container_in_docker(self, app: AppSettings = None):
        req = self.req
        # STEP - Fill in user_email if not present
        if not self.token.user_email:
            login_result = TableauCloudLogin.login(self.token, True)
            api = TCApiClient(login_result)
            get_or_fetch_site_id(api, self.token, self.logger)

        # STEP - Validate input
        if not self.validate_input():
            return

        if app.img_registry_type == ImageRegistryType.aws_ecr:
            reg = EcrRegistryPrivate(self.logger, app.ecr_private_aws_account_id, app.ecr_private_repository_name, app.aws_region, app.aws_profile)
            local_image_id = reg.pull_image_stream(app.selected_remote_image_tag, False, None)
            if not local_image_id:
                self.logger.info(f"unable to pull image from ecr.")
                return
        else:
            img = self.docker_client.get_image_details(app.selected_image_tag)
            if not img:
                self.logger.info(f"Local Bridge image named {app.selected_image_tag} is missing. Please Build first.")
                return
            else:
                local_image_id = img.short_id
        # STEP - check that PAT token is valid
        login_result = TableauCloudLogin.is_token_valid(self.token)
        if not login_result.is_success:
            self.logger.error(f"INVALID: PAT token {self.token.name} is not valid, please select a valid Personal Access Token name+secret")
            return

        bridge_container_name = BridgeContainerName.get_name(self.token.sitename, self.token.name)
        c = self.docker_client.get_container_by_name(bridge_container_name)
        if c:
            self.logger.info(f"INVALID: container already exists {bridge_container_name}.")
            return

        # STEP - Run Bridge Container
        agent_name = f"bridge_{self.token.name}"
        user_email = self.token.user_email
        pat_token_name = self.token.name
        pat_token_secret = self.token.secret
        tc_url = self.token.get_pod_url()
        self.logger.info(f"Bridge agent name: {agent_name}")

        labels = {
            ContainerLabels.tableau_pool_name: self.token.pool_name,
            ContainerLabels.tableau_pool_id: self.token.pool_id,
            ContainerLabels.tableau_bridge_agent_name: agent_name,
            ContainerLabels.tableau_sitename: self.token.sitename,
            ContainerLabels.tableau_server_url: tc_url,
            ContainerLabels.linux_distro: self.req.bridge.linux_distro,
            ContainerLabels.user_as_tableau: RunContainerAsUser.tableau if self.req.bridge.user_as_tableau else RunContainerAsUser.root,
        }
        if self.token.pool_id == DEFAULT_POOL:
            pool_id = ""
        else:
            pool_id = self.token.pool_id

        env_vars = {
            "AGENT_NAME": agent_name,
            "TC_SERVER_URL": tc_url,
            "SITE_NAME": self.token.sitename,
            "USER_EMAIL": user_email,
            "TOKEN_NAME": pat_token_name,
            # "TOKEN_ID": pat_token_name, #FutureDev: remove TOKEN_ID, this is only for old images
            "POOL_ID": pool_id,
        }

        dns_mappings = req.bridge.dns_mappings
        if dns_mappings:
            str_dns = "  ".join([f"{k}:{v}" for k, v in dns_mappings.items()])
            self.logger.info(f"DNS mappings: {str_dns}")
        volumes = None
        if req.bridge.unc_path_mappings:
            str_unc_display = str_unc = ""
            volumes = {}
            for unc_path, paths in req.bridge.unc_path_mappings.items():
                cont_mnt = paths[PropNames.container_mount_path]
                host_mnt = paths[PropNames.host_mount_path]
                str_unc_display += f"host path {host_mnt} mounted in container as {cont_mnt} and mapped to UNC file share path {unc_path}\n"
                str_unc += f"{unc_path}:{cont_mnt}\n"
                volumes[host_mnt] = {"bind": cont_mnt, "mode": "ro"}
            self.logger.info(f"UNC path mappings:\n{str_unc_display}")
            env_vars["UNC_PATH_MAPPINGS"] = str_unc
        network_mode = self.get_network_mode(req.bridge.docker_network_mode)
        env_vars["TOKEN_VALUE"] = pat_token_secret
        self.docker_client.run_bridge_container(local_image_id, bridge_container_name, labels, env_vars, volumes, dns_mappings, network_mode)
        return True

    @staticmethod
    def remove_bridge_container_in_docker(logger, bridge_container_name):
        docker_client = DockerClient(logger)
        details = docker_client.get_container_details(bridge_container_name, False)
        docker_client.stop_and_remove_container(bridge_container_name)
        admin_token = TokenLoader(logger).get_token_admin_pat()
        if not admin_token:
            return False
        agent_name = details.labels.get(ContainerLabels.tableau_bridge_agent_name)
        agent_sitename = details.labels.get(ContainerLabels.tableau_sitename)
        logger.info(f"Call Tableau Cloud API to remove agent {agent_name} from site {agent_sitename}")
        return BridgeStatusLogic(logger).remove_agent_with_tc_api(admin_token, agent_name, agent_sitename, logger)

    def validate_input(self):
        if not self.token:
            self.logger.warning(f"Token is empty")
            return False
        if not self.token.pool_id:
            self.logger.warning(f"Pool ID is required")
            return False
        if not self.token.pod_url:
            self.logger.warning(f"Tableau cloud server_url is required")
            return False
        if not self.token.sitename:
            self.logger.warning(f"Tableau cloud sitename is required")
            return False
        if not self.token.user_email:
            self.logger.warning(f"User email is required")
            return False
        #FutureDev: add more validation
        return True

    def get_network_mode(self, docker_network_mode):
        if docker_network_mode not in VALID_DOCKER_NETWORK_MODES:
            self.logger.info(f"docker_network_mode '{docker_network_mode}' is invalid, using default '{DEFAULT_DOCKER_NETWORK_MODE}'")
            return DEFAULT_DOCKER_NETWORK_MODE
        elif docker_network_mode != DEFAULT_DOCKER_NETWORK_MODE:
            self.logger.info(f"setting docker network_mode to '{docker_network_mode}'")
        return docker_network_mode

    def run_bridge_container_on_remote_host(self, remote_host: str, remote_username):
        # ref:   https://chatgpt.com/c/675f9d56-9998-8013-8985-956662f86ecf

        # STEP - docker export image to .tar and zip it
        img_tar_name = "image.tar"
        cmd = f"docker save <image-name> -o {img_tar_name}"
        cmd = f"gzip {img_tar_name}"  # gzip image.tar

        # STEP - scp zipped image to remote machine
        img_zip_name = "image.tar.gz"
        cmd = f"scp {img_zip_name} {remote_username}@{remote_host}:~/"  # scp image.tar.gz user@remote-host:/path/to/destination/

        # STEP - On the remote machine: unzip and load image to docker
        cmd = f"gunzip ~/{img_zip_name}"

        #   gunzip /path/to/destination/image.tar.gz
        cmd = f"docker load < ~/{img_zip_name}"

        #   docker load < /path/to/destination/image.tar

        # STEP - On the remote machine: run the container
        #  docker run -d --restart=on-failure:1 \


