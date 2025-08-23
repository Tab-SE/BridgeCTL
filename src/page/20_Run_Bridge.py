import streamlit as st

import streamlit as st

import src.token_loader
from src import bridge_settings_file_util
from src.azure_registry import AcrRegistry
from src.bridge_container_runner import BridgeContainerRunner
from src.docker_client import DockerClient
from src.ecr_registry_private import EcrRegistryPrivate
from src.enums import ImageRegistryType, ADMIN_PAT_PREFIX, DEFAULT_POOL
from src.lib.usage_logger import UsageMetric, USAGE_LOG
from src.models import AppSettings
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.pat_tokens_ui import add_pat_token_dialog, remove_pat_token_dialog
from src.page.ui_lib.shared_bridge_settings import load_and_select_tokens, \
    bridge_settings_view_mode_content, show_and_select_image_tags
from src.page.ui_lib.stream_logger import StreamLogger
from src.token_loader import TokenLoader


def start_run_bridge_container(token_names, cont_s, app: AppSettings):
    with st.spinner(""):
        for token_name in token_names:
            token = TokenLoader(StreamLogger(st.container())).get_token_by_name(token_name)
            if not token:
                cont_s.warning(f"INVALID: token_name {token_name} not found in {src.token_loader.token_file_path}")
                return
            req = bridge_settings_file_util.load_settings()
            runner = BridgeContainerRunner(StreamLogger(cont_s), req, token)
            is_success = runner.run_bridge_container_in_docker(app)
            if not is_success:
                return
            cont_s.success("Container Started")
        return True



def rerun_page():
    pass

def render_run_script(col1, app: AppSettings, selected_token_names):
    if app.streamlit_server_address and app.streamlit_server_address != "localhost":
        col1.warning("BridgeCTL Web UI server address is not 'localhost'. For security reasons the Show Run Script feature is only available on localhost")
        return
    cont=col1.container(height=900)
    s_logger= StreamLogger(cont)
    token_loader = TokenLoader(s_logger)
    bst = token_loader.load()
    if app.selected_image_tag:
        if app.img_registry_type == ImageRegistryType.aws_ecr:
            ecr_mgr = EcrRegistryPrivate(s_logger, app.ecr_private_aws_account_id, app.ecr_private_repository_name, app.aws_region, app.aws_profile)
            pull_image_script = ecr_mgr.pull_image_stream(app.selected_remote_image_tag, True, None)
            remote_img_tag = f"{app.ecr_private_aws_account_id}.dkr.ecr.{app.aws_region}.amazonaws.com/{app.ecr_private_repository_name}:{app.selected_remote_image_tag}"
        elif app.img_registry_type == ImageRegistryType.azure_acr:
            pull_image_script = AcrRegistry.pull_image_script(app)
            remote_img_tag = f"$ACR_LOGIN_SERVER/{app.selected_image_tag}"
        else:
            raise Exception(f"Unsupported image registry type {app.img_registry_type}")
    else:
        pull_image_script = ""
        remote_img_tag = ""
    # tag = app.selected_image_tag if app.selected_image_tag else 'latest'
    pool_id = "" if bst.site.pool_id in [None, DEFAULT_POOL] else bst.site.pool_id

    script_content = f"""
set -o errexit; set -o nounset; set -o xtrace

# STEP - Login to {app.img_registry_type} and pull image
{pull_image_script}

#STEP - Run bridge agents, one per PAT token
function run_container() {{
  docker run -d --restart=on-failure:1 \\
    --name "bridge_{bst.site.sitename}_${{TOKEN_NAME}}" \\
    -e AGENT_NAME="bridge_${{TOKEN_NAME}}" \\
    -e TC_SERVER_URL="{bst.site.pod_url}" \\
    -e SITE_NAME="{bst.site.sitename}" \\
    -e USER_EMAIL="{bst.site.user_email}" \\
    -e POOL_ID="{pool_id}" \\
    -e TOKEN_NAME="${{TOKEN_NAME}}" \\
    -e TOKEN_VALUE="${{TOKEN_VALUE}}" \\
    {remote_img_tag}
}}
"""

    if selected_token_names:
        for token_name in selected_token_names:
            token = token_loader.get_token_by_name(token_name)
            if not token:
                cont.warning(f"INVALID: token_name {token_name} not found in {src.token_loader.token_file_path}")
                continue
            script_content += f"""
TOKEN_NAME="{token.name}"
set +o xtrace
TOKEN_VALUE="{token.secret}"
set -o xtrace
run_container
"""
    else:
        script_content += f"""
TOKEN_NAME="<token name>"
set +o xtrace
TOKEN_VALUE="<token secret>"
set -o xtrace
run_container
"""
    cont.code(script_content, language='bash')

def run_bridge_container(existing_container_names):
    if not existing_container_names:
        existing_container_names = DockerClient(StreamLogger(st.container())).get_bridge_container_names()

    # st.markdown("#### :material/directions_run: Run")
    PageUtil.horizontal_radio_style()
    col1, col2 = st.columns([2,1])
    app = AppSettings.load_static()
    # col1.markdown("##### 🐳 Container Image")
    tag_is_valid = show_and_select_image_tags(col1, app)
    if app.img_registry_type == ImageRegistryType.aws_ecr or app.img_registry_type == ImageRegistryType.azure_acr:
        show_script = True # col1.checkbox("Show Run Script")
    else:
        show_script = False
    form = col1.form(key="st")
    selected_token_names, token_loader, tokens = load_and_select_tokens(form, existing_container_names)
    b_lbl = "Show Script for " if show_script else ""
    if form.form_submit_button(f"{b_lbl}Run Bridge Containers"):
        if show_script:
            render_run_script(col1, app, selected_token_names)
        else:
            if not selected_token_names:
                form.warning("Please select one or more PAT tokens")
            elif not tag_is_valid:
                form.warning("Please select a valid image tag")
            else:
                ret = start_run_bridge_container(selected_token_names, form, app)
                if ret:
                    st.button("Refresh 🔄", on_click=rerun_page)
                    USAGE_LOG.log_usage(UsageMetric.run_bridge_docker_container)

    col7, col8 = col1.columns([3,1])
    if col8.button("Add Token"):
        add_pat_token_dialog(None, token_loader)
    if col8.button("Remove Token"):
        remove_pat_token_dialog(None, token_loader)


def page_content():
    # with st.expander("ℹ️ Instructions", expanded=False):
    #     st.info(
    #         "To deploy bridge container images to kubernetes:\n"
    #         "1. Configure your kubernetes cluster in [Settings](/Settings?tab=k8s)\n"
    #         "2. Select a container image (build locally or from registry)\n"
    #         "3. Choose Personal Access Tokens (PAT) for the bridge agents\n"
    #         "4. Click Deploy to create the pods"
    #     )

    with st.expander("ℹ️ Instructions", expanded=False):
        st.info(
            f'- Add Personal Access Tokens (PAT): Navigate to the [Settings](/Settings) page and add a PAT token per bridge agent and one token starting with "{ADMIN_PAT_PREFIX}".\n'
            '- Select a Target Pool: Use the "Edit" button to select a target pool for the bridge agents.\n'
            '- Build Image: Build a local bridge container image on the [build](/Docker_-_Build) page or select an image from ECR.\n'
            '- Select Tokens: From the dropdown menu, select one or more tokens. Each bridge agent must be associated with a unique PAT token. The name of the bridge agent will be the same as the name of the selected token.\n'
            '- Run the Container: Press Run Container to run a local bridge on linux container.')
    with st.container(border=True):
        st.markdown(f'#### ⚙️ Target Bridge Pool')
        bridge_settings_view_mode_content()
    d_client = DockerClient(StreamLogger(st.container()))
    if not d_client.is_docker_available():
        return
    with st.spinner(""):
        existing_container_names = d_client.get_bridge_container_names()
        run_bridge_container(existing_container_names)


PageUtil.set_page_config("Run Bridge Containers", ":material/directions_run: Run Tableau Bridge Containers in Local Docker")
PageUtil.horizontal_radio_style()
page_content()
