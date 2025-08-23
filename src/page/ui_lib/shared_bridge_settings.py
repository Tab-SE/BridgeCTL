from time import sleep
from typing import List

import streamlit as st

from src import bridge_settings_file_util
from src.bridge_container_builder import buildimg_path
from src.bridge_rpm_download import BridgeRpmDownload
from src.cache_dto import CacheManagerEcrImageList, EcrImageListDto
from src.cli.bridge_status_logic import get_or_fetch_site_id
from src.docker_client import DockerClient, ContainerLabels
from src.ecr_registry_private import EcrRegistryPrivate
from src.enums import DEFAULT_POOL, ImageRegistryType
from src.k8s_client import K8sSettings
from src.lib.general_helper import StringUtils
from src.lib.tc_api_client import TableauCloudLogin, TCApiLogic, BridgePool
from src.models import AppSettings, BridgeRequest, BridgeRpmSource
from src.page.ui_lib.stream_logger import StreamLogger
from src.token_loader import TokenLoader



def show_unc_path_mappings(req: BridgeRequest, cont):
    if not req.bridge.unc_path_mappings:
        return
    upm = ",".join(req.bridge.unc_path_mappings.keys())
    cont.markdown(f"UNC Path Mappings: `{len(req.bridge.unc_path_mappings)}`", help=f"{upm}")
    if req.bridge.bridge_rpm_source == BridgeRpmSource.tableau_com:
        if req.bridge.bridge_rpm_version_tableau_com < "20251":
            cont.warning("UNC Path Mappings are only supported in Bridge version 2025.1 and later")
    else:
        rpm_download = BridgeRpmDownload(StreamLogger(cont), req.bridge.bridge_rpm_source, buildimg_path)
        rpm_downloaded = rpm_download.get_rpm_filename_already_downloaded()
        ver = rpm_download.get_version_from_filename(rpm_downloaded)
        ver_date = ver.replace("main.","")
        min_ver = "24.1030"
        if ver_date < min_ver:
            cont.warning(f"UNC Path Mappings are only supported in Bridge version {min_ver} and later")

def bridge_settings_view_mode_content():
    cont = st.container()
    bst = TokenLoader(StreamLogger(cont)).load()
    req = bridge_settings_file_util.load_settings()
    col1, col2 = cont.columns([1, 2])
    col1.markdown(f"Pool: **`{bst.site.pool_name}`**")
    col2.markdown(f"🌐 Site: **`{bst.site.sitename}`**")
    show_unc_path_mappings(req, col2)
    if col1.button("Edit"):
        edit_mode_dialog()

@st.dialog("Select Bridge Pool", width="large")
def edit_mode_dialog():
    token_loader = TokenLoader(StreamLogger(st.container()))
    # req = bridge_settings_file_util.load_settings()
    admin_pat = token_loader.get_token_admin_pat()
    if not admin_pat:
        st.html(f"You can add PAT tokens on the <a href='/Settings'>Settings</a> page")
    else:
        with st.spinner("Fetching bridge pool information from Tableau API"):
            login_result = TableauCloudLogin.login(admin_pat, True)
            logic = TCApiLogic(login_result)
            with st.form(key="edit_bridge_pool", border=False):
                site_id = get_or_fetch_site_id(logic.api, admin_pat, StreamLogger(st.container()))
                pool_list = logic.get_pool_list(site_id)
                pool_list.insert(0, BridgePool(DEFAULT_POOL, DEFAULT_POOL))
                user_email = admin_pat.user_email
                col1, col2 = st.columns([2,3])
                idx = next((i for i, member in enumerate(pool_list) if member.id == admin_pat.pool_id), 0)
                selected_pool = col1.selectbox("Bridge Pool", pool_list, format_func= lambda x: x.name, placeholder="Select a pool", index= idx, help=f"Select a pool from the [Bridge settings page]({admin_pat.get_bridge_settings_url()})")
                col2.markdown(f"🌐 Tableau Cloud Site: `{admin_pat.sitename}`")
                col2.markdown(f"`{admin_pat.pod_url}`")
                col2.markdown(f"User email: `{user_email}`") # FutureDev: add a way to change user email
                col2.markdown(f"Pool: `{admin_pat.pool_name}`")
                col2.markdown(f"Pool ID: `{admin_pat.pool_id}`")

                if st.form_submit_button("Confirm and Save"):
                    if not selected_pool:
                        col1.warning("Pool is required")
                    else:
                        token_loader.update_pool_id(selected_pool.id, selected_pool.name)
                        # pool_id = selected_pool.id
                        # req.bridge.pool_name = selected_pool.name
                        # req.bridge.user_email = user_email
                        # req.bridge.pod_url = admin_pat.pod_url
                        # req.bridge.site_name = admin_pat.sitename.lower()
                        # bridge_settings_file_util.save_settings(req)
                        st.success("Saved")
                        sleep(.7)
                        st.rerun()

@st.dialog("Refresh ECR Image Cache", width="large")
def show_dialog_ecr_image_cache_refresh(app: AppSettings):
    st.info("Fetching Image List from ECR Container Repository. Note that you must have valid local AWS credentials for fetching from ECR.")
    cont_e = st.empty()
    try:
        dto = CacheManagerEcrImageList.load()
        if dto.is_valid():
            cont_e.markdown(f"Last refreshed **{StringUtils.short_time_ago(dto.last_updated)}** ago")
    except Exception as e:
        st.error(f"Error loading cache: {e}")
    with st.spinner(""):
        ecr_mgr = EcrRegistryPrivate(StreamLogger(st.container()), app.ecr_private_aws_account_id, app.ecr_private_repository_name, app.aws_region, app.aws_profile)
        tags, error = ecr_mgr.list_ecr_repository_tags()
        if not error:
            dto = EcrImageListDto(tags = tags)
            CacheManagerEcrImageList.save(dto)
            cont_e.markdown(f"Last refreshed **just now**")
            st.success(f"ECR Image Cache Refreshed. {len(dto.tags)} tags found")
        else:
            st.error("Error fetching tags from ECR")
        st.page_link("src/page/52_Publish_Image.py", label="Close")

def render_image_cache_refresh_dialog_button(app, cont) -> (str, bool):
    if cont.button("Refresh ECR Image Cache"):
        show_dialog_ecr_image_cache_refresh(app)

def select_image_tags_from_ecr_cache(cont, is_publish_page = False) -> (str, bool):
    dto = CacheManagerEcrImageList.load()
    l = f"🐳 AWS ECR Images (refreshed {StringUtils.short_time_ago(dto.last_updated)} ago)" if dto.is_valid() else "ECR Image Cache not yet loaded"
    if not dto.is_valid() and not is_publish_page:
        l += ", go to [Publish Image](/Publish_Image) to refresh"
    c = cont.selectbox(l, dto.tags)
    return c, dto.is_valid()

def show_and_select_image_tags(cont, app: AppSettings):
    # PageUtil.horizontal_radio_style()
    if not app.is_ecr_configured() and not app.azure_acr_enabled:
        img_reg_type = ImageRegistryType.local_docker
    else:
        options = [ImageRegistryType.local_docker]
        if app.is_ecr_configured():
            options.append(ImageRegistryType.aws_ecr)
        if app.azure_acr_enabled:
            options.append(ImageRegistryType.azure_acr)
        idx = options.index(app.img_registry_type) if app.img_registry_type in options else 0
        img_reg_type = cont.radio("Container Image Registry", options, index=idx)
    if img_reg_type != app.img_registry_type:
        app.img_registry_type = img_reg_type
        app.save()
    if app.img_registry_type == ImageRegistryType.aws_ecr:
        selected_remote_image_tag, is_valid = select_image_tags_from_ecr_cache(cont)
        if app.selected_remote_image_tag != selected_remote_image_tag:
            app.selected_remote_image_tag = selected_remote_image_tag
            app.save()
    else:
        selected_image_tag, is_valid = select_image_tags_local(app, cont)
        if app.selected_image_tag != selected_image_tag:
            app.selected_image_tag = selected_image_tag
            app.save()
    return is_valid

def select_image_tags_local(app: AppSettings, cont, no_label: bool = False):
    tags = DockerClient(StreamLogger(st.container())).get_tableau_bridge_image_names()
    idx = 0 if app.selected_image_tag not in tags else tags.index(app.selected_image_tag)
    selected_tag = cont.selectbox("🐳 Select Local Bridge Image", tags, index=idx, label_visibility="collapsed" if no_label else "visible")
    if not tags:
        cont.warning("Please build bridge image")
        return None, False
    return selected_tag, True

def load_and_select_tokens(cont, existing_container_names, is_docker: bool = True) -> (List[str], TokenLoader, List):
    selected_token_names = None
    token_loader = TokenLoader(StreamLogger(cont))
    available_token_names, in_use_token_names, tokens = token_loader.get_available_tokens(existing_container_names)
    if len(available_token_names) > 0:
        available_token_names.insert(0, "")
        col1, col2 = cont.columns([2, 1])
        selected_token_names = col1.multiselect("🔑 Select PAT Tokens", available_token_names)
    else:
        cont.warning("Please add PAT tokens. One PAT Token is required per bridge agent.")
    runtime = "local docker" if is_docker else "kubernetes"
    cont.columns([1,2])[1].caption(f"tokens in use in {runtime}: " + ', '.join(in_use_token_names))
    return selected_token_names, token_loader, tokens

def show_k8s_context(cont, show_link=True) -> bool:
    app = AppSettings.load_static()
    cont.markdown(f'#### Target Kubernetes Context')
    context, server_url = K8sSettings.get_current_k8s_context_name()
    if not context or not server_url:
        cont.warning(f"Context and Server URL cant be detected from k8s config: {K8sSettings.kube_config_path}")
        return False

    # col1b, col2b, col2c = cont.columns([1, 1, 1])
    l = "[Change Context](/Settings?tab=k8s)" if show_link else ""
    cont.markdown(f"K8s context: `{context}` {l}", help=f"K8s Server URL: `{server_url}`")
    cont.markdown(f"namespace: `{app.k8s_namespace}`")
    return True

def show_image_created(cont, img_detail):
    try:
        sz = f", Size: *{img_detail.size_gb} GB*"
        created_dte = StringUtils.parse_time_string(img_detail.created)
        ago = StringUtils.short_time_ago(created_dte)
        cont.markdown(f"  Image Created: *{ago} ago*{sz}")
    except ValueError as e:
        cont.markdown(f"  Image Created: *{e}*")

def render_image_details(cont, d_client: DockerClient, local_image_name, img_detail = None):
    if not local_image_name:
        return
    show_created = False
    if not img_detail:
        img_detail = d_client.get_image_details(local_image_name)
        show_created = True
    with cont.expander("**Local Image Detail**"):
        if not img_detail:
            st.warning(f"Local Bridge image named {img_detail.image_name} is missing. Please Build first.")
            return
        st.write(f"Image ID: `{img_detail.short_id}`")
        st.write(f"Tags: `{', '.join(img_detail.tags)}`")
        if show_created:
            show_image_created(st, img_detail)
        str_labels = ""
        for a in dir(ContainerLabels):
            if not a.startswith("__"):
                value = img_detail.labels.get(a)
                if value:
                    str_labels += f"- {a}: `{value}`\n"
        st.write(f"Used by containers: `{img_detail.used_by_containers if img_detail.used_by_containers else 'None'}`")
        st.write(f"Labels: \n{str_labels}")