from src.docker_client import ContainerLabels
from src.ecr_registry_private import EcrRegistryPrivate
from src.enums import BridgeContainerName
from src.k8s_client import K8sClient
from src.lib.tc_api_client import TableauCloudLogin
from src.models import LoggerInterface, AppSettings
from src.token_loader import TokenLoader


class K8sBridgeManager:
    def __init__(self, logger: LoggerInterface, req, app: AppSettings):
        self.logger = logger
        self.req = req
        self.k8s_client = K8sClient()
        self.app = app

    def run_bridge_container_in_k8s(self, token_name, image_tag, image_pull_policy: str = "Always") -> str:
        req = self.req
        token = TokenLoader(self.logger).get_token_by_name(token_name)
        if not token:
            return f"INVALID: token is empty"
        #FutureDev: additional validation ...

        # if token.sitename != req.bridge.site_name:
        #     return f"bridge.sitename '{req.bridge.site_name}' setting does not match token sitename {token.sitename}"
        self.logger.info(f"check that PAT token {token.name} is valid")
        login_result = TableauCloudLogin.is_token_valid(token)
        if not login_result.is_success:
            return f"INVALID: PAT token {token.name} is not valid, please select a valid Personal Access Token name+secret"

        bridge_container_name = BridgeContainerName.get_name(token.sitename, token.name)
        if not self.k8s_client.namespace_exists(self.app.k8s_namespace):
            ret = self.k8s_client.create_namespace(self.app.k8s_namespace)
            self.logger.info(f"created namespace {self.app.k8s_namespace}")

        agent_name = bridge_container_name
        user_email = token.user_email
        pat_token_name = token.name
        pat_token_secret = token.secret
        tc_url = token.get_pod_url()
        self.logger.info(f"Bridge agent name: {agent_name}, Image: {image_tag}")
        self.logger.info(f"Pool: {token.pool_name}")
        labels = {
            ContainerLabels.tableau_pool_name: token.pool_name,
            ContainerLabels.tableau_pool_id: token.pool_id,
            ContainerLabels.tableau_bridge_agent_name: agent_name,
            ContainerLabels.tableau_sitename: token.sitename,
            ContainerLabels.tableau_server_url: tc_url.replace("https://", ""),
            ContainerLabels.database_drivers: "0",
            ContainerLabels.tableau_bridge_rpm_source: req.bridge.bridge_rpm_source,
            ContainerLabels.user_as_tableau: str(req.bridge.user_as_tableau),
        }
        env_vars = {
            "AGENT_NAME": agent_name,
            "TC_SERVER_URL": tc_url,
            "SITE_NAME": token.sitename,
            "USER_EMAIL": user_email,
            "TOKEN_NAME": pat_token_name,
            "TOKEN_VALUE": pat_token_secret,
            "POOL_ID": token.pool_id,
        }
        if image_pull_policy == "Always":
            registry_image_url = EcrRegistryPrivate.get_image_url_static(self.logger, image_tag)
        else:
            registry_image_url = image_tag
        return self.k8s_client.create_bridge_pod(self.app.k8s_namespace, bridge_container_name, registry_image_url, env_vars, labels, image_pull_policy)
