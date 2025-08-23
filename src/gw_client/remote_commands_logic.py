from src.bridge_container_runner import BridgeContainerRunner
from src.gw_client.dc_gw_client import DcGwClient
from src.gw_client.dc_gw_client_models import RemoteCommand, GwActions, UpdateCommandDto, ActionState, \
    ActionResults, ParamNames
from src.token_loader import TokenLoader
from src import bridge_settings_file_util
from src.models import AppSettings, LoggerInterface


class RemoteCommandLogic:
    def __init__(self, logger: LoggerInterface):
        self.logger = logger

    def route_command(self, command: RemoteCommand):
        bst = TokenLoader(self.logger).load()
        gw = DcGwClient(bst.site.gw_api_token)
        try:
            gw.update_command(UpdateCommandDto(command.id, ActionState.started))
            if command.action == GwActions.add_bridge_agent:
                result, detail = self.add_bridge_agent(command)
            elif command.action == GwActions.remove_bridge_agent:
                result, detail = self.remove_bridge_agent(command)
            else:
                self.logger.error(f"unknown action {command.action}")
                result = ActionResults.failed
                detail = f"unknown action {command.action}"
        except Exception as e:
            self.logger.error(f"error in route_command: {e}. command: {command}")
            result = ActionResults.failed
            detail = f"error in route_command: {e}"
        gw.update_command(UpdateCommandDto(command.id, ActionState.completed, result, detail))
        return result, detail

    def add_bridge_agent(self, command: RemoteCommand):
        req = bridge_settings_file_util.load_settings()
        tokens = TokenLoader(self.logger).load_tokens()
        if not tokens:
            self.logger.error("No tokens found in bridge_tokens.yml")
            return ActionResults.failed, "No tokens found in bridge_tokens.yml"
        token = [t for t in tokens if not t.is_admin_token()]
        if token:
            token = token[-1]
        if not token:
            self.logger.info(f"no available bridge token found in bridge_tokens.yml")
            return ActionResults.failed, "no available bridge token found in bridge_tokens.yml"
        app = AppSettings.load_static()
        runner = BridgeContainerRunner(self.logger, req, token)
        is_success = runner.run_bridge_container_in_docker(app)
        result = ActionResults.success if is_success else ActionResults.failed
        detail = "new bridge agent created"
        return result, detail

    def remove_bridge_agent(self, command: RemoteCommand):
        bridge_container_name = command.parameters[ParamNames.bridge_container_name]
        BridgeContainerRunner.remove_bridge_container_in_docker(self.logger, bridge_container_name)
        result = ActionResults.success
        detail = f"bridge agent {bridge_container_name} removed"
        return result, detail
