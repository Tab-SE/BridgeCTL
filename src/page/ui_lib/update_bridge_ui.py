from dataclasses import dataclass

import streamlit as st

from src import bridge_settings_file_util
from src.bridge_container_builder import BridgeContainerBuilder
from src.bridge_container_runner import BridgeContainerRunner
from src.docker_client import DockerClient, ContainerLabels
from src.enums import BridgeContainerName
from src.models import AppSettings
from src.page.ui_lib.shared_bridge_settings import select_image_tags_local
from src.page.ui_lib.stream_logger import StreamLogger
from src.token_loader import TokenLoader


@st.dialog("Update Bridge Containers to New Image", width="large")
def show_upgrade_dialog():
    st.info(f"""
    Update multiple bridge agents in Docker. The old containers will be removed and a new container will be started using the new image but with the same Pool and PAT Token settings.
    Bridge containers targeting a different pool will not be updated. Note that bridge logs inside the container will not be retained. 
    Also note that sometimes PAT tokens become invalid but it does not become obvious until a container is restarted. If this happens simply create a new replacement PAT token from the Tableau UI.""")
    app = AppSettings.load_static()
    admin_pat = TokenLoader(StreamLogger(st.container())).get_token_admin_pat()
    if not admin_pat:
        return
    cont = st.container(border=True)
    cont.markdown(f"Update containers to this Local Image:")
    selected_image_tag, is_valid = select_image_tags_local(app, cont, True)
    if not selected_image_tag:
        return
    # get list of local bridge containers
    docker_client = DockerClient(StreamLogger(st.container()))
    containers = docker_client.get_containers_list(DockerClient.bridge_prefix)

    containers_to_update = []
    containers_skip_update = []
    containers_already_updated = []
    for c in containers:
        pool_id = c.labels.get(ContainerLabels.tableau_pool_id)
        site_name = c.labels.get(ContainerLabels.tableau_sitename)
        image_tags = c.image.attrs.get("RepoTags")
        image_name = image_tags[0] if image_tags else None
        bc = BridgeContainerToUpgrade(c.name,
                                      c.labels.get(ContainerLabels.tableau_sitename),
                                      c.labels.get(ContainerLabels.tableau_pool_id),
                                      c.labels.get(ContainerLabels.tableau_pool_name),
                                      image_name)
        if pool_id == admin_pat.pool_id and site_name == admin_pat.sitename:
            if bc.image_name != selected_image_tag:
                containers_to_update.append(bc)
            else:
                containers_already_updated.append(bc)
        else:
            containers_skip_update.append(bc)

    # col1, col2 = cont.columns([1,2])
    cont.markdown(f"Target Site: `{admin_pat.sitename}`")
    cont.markdown(f"Target Pool: `{admin_pat.pool_name}`")
    st.markdown(f"**Bridge containers to update:**")
    if containers_to_update:
        for bc in containers_to_update:
            st.markdown(f"  - `{bc.name}` {bc.image_name}")
    else:
        st.info(f"No Bridge containers to update")
    if containers_already_updated:
        already = ','.join([c.name for c in containers_already_updated])
        st.caption(f"Bridge containers already using the selected image: {already}")

    if containers_skip_update:
        st.markdown(f"**Bridge containers will not be updated (different pool):**")
        for bc in containers_skip_update:
            st.markdown(f"  - `{bc.name}`: Pool `{bc.pool_name}`")
    if not is_valid:
        return
    if app.selected_image_tag != selected_image_tag:
        app.selected_image_tag = selected_image_tag
        app.save()

    req = bridge_settings_file_util.load_settings()
    num = len(containers_to_update)
    if st.button(f"Update containers to new image", disabled=num == 0):
        with st.spinner(""):
            cont_s = st.container()
            for bc in containers_to_update:
                bc: BridgeContainerToUpgrade = bc
                if bc.image_name == app.selected_image_tag:
                    cont_s.info(f"Container `{bc.name}` already using image")
                    continue
                logger = StreamLogger(cont_s)
                BridgeContainerRunner.remove_bridge_container_in_docker(logger, bc.name)
                token = TokenLoader(StreamLogger(cont_s)).get_token_by_name(bc.get_token_name())
                if not token:
                    cont_s.warning(f"Token {bc.get_token_name()} not found.")
                    continue
                runner = BridgeContainerRunner(StreamLogger(cont_s), req, token)
                is_success = runner.run_bridge_container_in_docker(app)
                if not is_success:
                    cont_s.warning("Container Not Started")
                else:
                    cont_s.success("Container Started")


@dataclass
class BridgeContainerToUpgrade:
    name: str
    site_name: str
    pool_id: str
    pool_name: str
    image_name: str = None

    def get_token_name(self):
        token_name = BridgeContainerName.get_token_name(self.name, self.site_name)
        return token_name


@st.dialog("Scale Bridge Containers in Local Docker", width="large")
def show_scale_up_dialog():
    st.info(f"""
    Select a target number of bridge containers.""")
    app = AppSettings.load_static()
    admin_pat = TokenLoader(StreamLogger(st.container())).get_token_admin_pat()
    if not admin_pat:
        return
    cont = st.container(border=True)
    options = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
    idx = app.manage_docker_containers_target_count if app.manage_docker_containers_target_count in options else 0
    target_count = cont.columns(3)[0].selectbox("Target Bridge Containers Count", options, index =idx)
    if target_count != app.manage_docker_containers_target_count:
        app.manage_docker_containers_target_count = target_count
        app.save()
    c1,c2 = cont.columns([2,1])
    c1.markdown(f"Target Site: `{admin_pat.sitename}` Pool: `{admin_pat.pool_name}`")
    c2.page_link("src/page/20_Run_Bridge.py", label="edit", help="Edit pool or image from the Run Bridge page.")
    if not app.selected_image_tag:
        cont.warning("please build the bridge image first")
        return
    cont.markdown(f"Target Local Image: `{app.selected_image_tag}`")
    docker_client = DockerClient(StreamLogger(st.container()))
    bridge_containers = docker_client.get_containers_list(DockerClient.bridge_prefix)
    current_count = len(bridge_containers)
    cont.markdown(f"Current Bridge Container Count: `{current_count}`")
    req = bridge_settings_file_util.load_settings()
    count_to_add = target_count - current_count
    existing_container_names = docker_client.get_bridge_container_names()
    token_loader = TokenLoader(StreamLogger(st.container()))
    available_token_names, in_use_token_names, tokens = token_loader.get_available_tokens(existing_container_names)
    available_token_count = len(available_token_names)
    a = f"added. `{available_token_count}` tokens are available." if count_to_add >= 0 else "removed."
    s = "" if abs(count_to_add) == 1 else "s"
    cont.markdown(f"`{abs(count_to_add)}` Container{s} will be {a}")
    if count_to_add > available_token_count:
        cont.warning(f"Insufficient available tokens to add {count_to_add} container{s}. Can add {available_token_count}.")
    if count_to_add >= 0:
        if count_to_add == 0:
            st.info("No containers to add")
        effective_count = count_to_add if count_to_add <= available_token_count else available_token_count
        if st.button(f"Add {effective_count} containers", disabled=bool(count_to_add) == 0):
            with st.spinner(""):
                logger = StreamLogger(st.container())
                for i in range(count_to_add):
                    if not available_token_names:
                        logger.info(f"No available Tokens found, unable to add agent container.")
                        break
                    token_name = available_token_names.pop(0)
                    token = token_loader.get_token_by_name(token_name)
                    logger.info(f"Adding agent container {BridgeContainerName.get_name(token.sitename, token_name)}")
                    runner = BridgeContainerRunner(logger, req, token)
                    is_success = runner.run_bridge_container_in_docker(app)
                    if is_success:
                        logger.info("SUCCESS: Container Started")
                    else:
                        logger.warning("Container Not Started")
                st.page_link("src/page/50_Manage_Bridge.py", label="Close")
    else:
        count_to_remove = -1 * count_to_add
        containers = docker_client.get_containers_list(DockerClient.bridge_prefix)
        names_to_remove = []
        for i in range(count_to_remove):
            names_to_remove.append(containers.pop(-1).name)
        st.info(f"Removing the oldest containers: {','.join(names_to_remove)}")
        if st.button(f"Remove {count_to_remove} containers"):
            with st.spinner(""):
                logger = StreamLogger(st.container())
                for name in names_to_remove:
                   BridgeContainerRunner.remove_bridge_container_in_docker(logger, name)
                st.page_link("src/page/50_Manage_Bridge.py", label="Close")


