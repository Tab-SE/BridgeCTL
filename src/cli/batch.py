import argparse

import src.token_loader
from src.bridge_container_runner import BridgeContainerRunner
from src.cli.app_config import APP_CONFIG
from src.cli.app_logger import LOGGER
from src import bridge_settings_file_util
from src.bridge_container_builder import BridgeContainerBuilder
from src.cli import version_check, bridge_status_logic
from src.cli.bridge_status_logic import BridgeStatusLogic
from src.cli.version_check import check_latest_and_get_version_message
from src.ecr_registry_private import EcrRegistryPrivate
from src.enums import BridgeContainerName
from src.models import AppSettings, BridgeImageName
from src.token_loader import TokenLoader
from src.lib.tc_api_client import TableauCloudLogin, TCApiClient
from src.docker_client import DockerClient
import sys

def process_args():
    LOGGER.info("running in batch mode. parameters provided: " + str(' '.join(sys.argv[1:])))
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(f"--build", help="Build bridge container", action='store_true')
    group.add_argument(f"--push_image", help="Publish bridge container image to AWS ECR Container Registry", action='store_true')
    group.add_argument(f"--run", help="Run bridge container (and build if image not found)", action='store_true')
    group.add_argument(f"--remove", help="Remove a bridge container and unregister", action='store_true')
    group.add_argument(f"--update", help="Update BridgeCTL if a newer version is available", action='store_true')
    group.add_argument(f"--status", help="get status of bridge agents", action='store_true')
    group.add_argument(f"--remove_agent", help="remove bridge agent container with --agent_name", action='store_true')
    parser.add_argument(f"--token", help ="Specify a token name to use from config/bridge_tokens.yml for the --run or --remove commands", type=str)
    parser.add_argument(f"--agent_name", help ="Specify a agent container name for the --remove command", type=str)
    group.add_argument(f"--init_settings", help="initialize app_settings.yml and bridge_settings.yml", action='store_true')

    args = parser.parse_args()
    token_loader = TokenLoader(LOGGER)
    if args.build:
        req = bridge_settings_file_util.load_settings()
        BridgeContainerBuilder(None, req).build_bridge_image()
    elif args.push_image:
        push_bridge_image()
    elif args.run or args.remove:
        if not args.token:
            k = "run" if args.run else "remove"
            LOGGER.error(f"--token argument is required with --{k}")
            exit(1)
        req = bridge_settings_file_util.load_settings()
        token = token_loader.get_token_by_name(args.token)
        if not token:
            LOGGER.info(f"INVALID: token_name {args.token} not found in {src.token_loader.token_file_path}")
            return
        runner = BridgeContainerRunner(LOGGER, req, token)
        if args.run:
            app = AppSettings.load_static()
            runner.run_bridge_container_in_docker(app)
        elif args.remove:
            container_name = BridgeContainerName.get_name(token.sitename, token.name)
            BridgeContainerRunner.remove_bridge_container_in_docker(LOGGER, container_name)
    elif args.update:
        vmsg, latest_ver = check_latest_and_get_version_message()
        LOGGER.info_rich(f"version {APP_CONFIG.app_version} {vmsg}")
        did_it = version_check.update_if_new(True)
        if not did_it:
            LOGGER.info("No update available")
    elif args.status:
        token = token_loader.get_token_admin_pat()
        status = bridge_status_logic.display_bridge_status(token, LOGGER, False)
        print(status)
    elif args.remove_agent:
        if not args.agent_name:
            LOGGER.error(f"--agent_name argument is required with --remove_agent")
            exit(1)
        token = token_loader.get_token_admin_pat()
        agent_sitename = token.sitename # futureDev: fix this to get the sitename label of the agent
        BridgeStatusLogic(LOGGER).remove_agent_with_tc_api(token, args.agent_name, agent_sitename, LOGGER)
    elif args.init_settings:
        LOGGER.info("initialing config/app_settings.yml and bridge_settings.yml if they don't already exist")
        app = AppSettings()
        app.load()
        app.save()
        req = bridge_settings_file_util.load_settings()

# def get_tc_site_info():
#     token = TokenLoader(LOGGER).get_token_admin_pat()
#     login_result = TableauCloudLogin.login(token, False)
#
#     api = TCApiClient(login_result)
#     info = api.get_session_info()
#     print(info)
#     site_id = info['result']['site']['id']
#     agent_statuses = api.get_edge_pools(site_id)
#     print(agent_statuses)

def push_bridge_image():
    docker_client = DockerClient(LOGGER)
    req = bridge_settings_file_util.load_settings()
    app = AppSettings.load_static()
    reg = EcrRegistryPrivate(LOGGER, app.ecr_private_aws_account_id, app.ecr_private_repository_name, app.aws_region, app.aws_profile)
    reg.push_image(BridgeImageName.local_image_name(req), docker_client, False)
