from src.models import LoggerInterface, AppSettings


class AcrRegistry:
    def __init__(self, logger: LoggerInterface, registry_name, resource_group):
        self.logger = logger
        self.registry_name = registry_name
        self.resource_group = resource_group

    @staticmethod
    def pull_image_script(app: AppSettings):
        script = f"""az acr login --name {app.azure_acr_name}
ACR_LOGIN_SERVER=$(az acr show --name {app.azure_acr_name} --resource-group {app.azure_acr_resource_group} --query "loginServer" --output tsv)
docker pull $ACR_LOGIN_SERVER/{app.selected_image_tag}"""
        return script
