import re

import streamlit as st

from src import bridge_settings_file_util
from src.dataconnect_registry import DataConnectRegistryLogic, DCRegistry
from src.docker_client import DockerClient, ImageDetail
from src.models import AppSettings, BridgeImageName
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.shared_bridge_settings import show_image_created
from src.page.ui_lib.stream_logger import StreamLogger


@st.dialog("Data Connect Registry Settings", width="large")
def show_dc_registry_dialog(app: AppSettings, dc_reg: DCRegistry):
    with st.container(border=True):
        col1, col2 = st.columns([1,3])
        col1.markdown("**Hostname:**") 
        col2.markdown(f"`{dc_reg.hostname}`")
        col1.markdown("**IP Address:**", help="The IP address of the Data Connect registry")
        col1.write("")
        dc_ip_address = col2.text_input("IP Address", app.dataconnect_registry_ip_address, label_visibility="collapsed")
        col1.markdown("**Username:**")
        col2.markdown(f"`{dc_reg.username}`")
        col1.markdown("**Password:**", help="The password of the Data Connect registry. You can get this from the Tableau Cloud Data Connect UI")
        dc_reg_secret = col2.text_input("Password", app.dataconnect_registry_secret, type="password", label_visibility="collapsed")
        col1.write("")
        col1.markdown("**Pool ID:**", help="In the Tableau Cloud UI, click on the DataConnect pool name to get the Pool ID and enter it here. This will be used when publishing the image to DataConnect")
        dc_pool_id = col2.text_input("Pool ID", app.dataconnect_pool_id, label_visibility="collapsed")
        req = bridge_settings_file_util.load_settings()
        is_only_db_drivers = st.checkbox("Build image with only drivers, no bridge rpm", value=req.bridge.only_db_drivers)

        is_disabled = dc_ip_address == app.dataconnect_registry_ip_address and \
            dc_reg_secret == app.dataconnect_registry_secret and \
            dc_pool_id == app.dataconnect_pool_id and \
            is_only_db_drivers == req.bridge.only_db_drivers

        if st.button("Save Settings", use_container_width=True, disabled=is_disabled):
            app.dataconnect_registry_secret = dc_reg_secret
            app.dataconnect_registry_ip_address = dc_ip_address
            app.dataconnect_pool_id = dc_pool_id

            if is_only_db_drivers != req.bridge.only_db_drivers:
                req.bridge.only_db_drivers = is_only_db_drivers
                bridge_settings_file_util.save_settings(req)
            app.save()
            st.rerun()

def list_images_in_registry(cb1, dc_reg:DCRegistry, app: AppSettings):
    if cb1.button("List Images in Container Registry"):
        with st.spinner("listing images ..."):
            registry_logic = DataConnectRegistryLogic(StreamLogger(st.container()), dc_reg)
            repos = registry_logic.get_repos_with_tags()
            images_disp = ""
            for repo in repos:
                images_disp += f"\n- {repo.repo_name}"
                for t in repo.tags:
                    images_disp += f"\n  - {t}"

            # if ret.status_code == 200:
            #     images = ret.json().get("repositories", [])
            #     for i, img in enumerate(images):
            #         images_disp += f"\n- {img}:"
            #         url = f"https://{dc_reg.hostname}/v2/{img}/tags/list"
            #         ret_tags = requests.get(url, auth=(dc_reg.username, dc_reg.password))
            #         if ret_tags.status_code == 200:
            #             tags = ret_tags.json().get("tags", [])
            #             tags_disp = ", ".join(tags)
            #             images_disp += f"{tags_disp}"
            #         else:
            #             cb1.error(f"Error: {ret_tags.status_code}")
            cb1.write(images_disp)
            # else:
            #     cb1.error(f"Error: {ret.status_code}")


@st.dialog("Publish to Registry", width="large")
def show_push_dialog(img_name: str, app: AppSettings, dc_reg: DCRegistry):
    if not app.dataconnect_pool_id:
        st.error("Data Connect Pool ID is required")
        return
        
    registry_logic = DataConnectRegistryLogic(StreamLogger(st.container()), dc_reg)
    cmds = registry_logic.get_push_script(img_name, app.dataconnect_pool_id)
    st.code("\n".join(cmds), language='bash')

def push_image_to_container_registry(col1, img_name: str, app: AppSettings, dc_reg: DCRegistry, img_detail: ImageDetail):
    if col1.button("🚀 Publish to Registry →", 
                   disabled=not img_detail, 
                   use_container_width=True):
        show_push_dialog(img_name, app, dc_reg)

def get_ip_address(hostname: str) -> str:
    try:
        with open("/etc/hosts") as f:
            hosts = f.readlines()
        for line in hosts:
            if hostname in line:
                match = re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', line)
                if match:
                    return match.group(0)
    except Exception as e:
        st.error(f"Error reading /etc/hosts: {e}")
    return None


def page_content():
    st.info("Instructions: Use this page to build and publish the container base image to the Data Connect Container Registry. \n\n"
              "The image will include database drivers and be based on the correct base image (redhat9).")

    docker_client = DockerClient(StreamLogger(st.container()))
    if not docker_client.is_docker_available():
        st.stop()

    col1, col2 = st.columns(2)
    col2.markdown("### Data Connect Container Registry")
    app = AppSettings.load_static()
    dc_reg = DCRegistry(password=app.dataconnect_registry_secret)
    req = bridge_settings_file_util.load_settings()
    # c1, c2 = col2.columns([1, 1])
    col2.markdown(f"`{dc_reg.hostname}` -> `{get_ip_address(dc_reg.hostname)}`")
    col2.markdown(f"Base Image Target Pool ID: `{app.dataconnect_pool_id}`")
    if col2.button("Edit"):
        show_dc_registry_dialog(app, dc_reg)

    # Left column - Built Image Details
    with col1:
        st.markdown("### Local Base Image Details")
        req.bridge.only_db_drivers = True
        img_name = BridgeImageName.local_image_name(req)
        img_detail = docker_client.get_image_details(img_name)
        if img_detail is None:
            st.write(f"No image labeled *{img_name}*")
        else:
            with st.container(border=True):
                st.markdown(f"Local Image Name: *{img_name}*")
                st.markdown(f"Database Drivers: *{img_detail.database_drivers}*")
                show_image_created(st.container(), img_detail)

    # Right column - List Images in Registry
    with col2:
        st.markdown("### Registry Images")
        if st.button("List Images in Registry", use_container_width=True):
            with st.spinner("Listing images..."):
                registry_logic = DataConnectRegistryLogic(StreamLogger(st.container()), dc_reg)
                repos_tags = registry_logic.get_repos_with_tags()
                if repos_tags:
                    with st.container(border=True):
                        for repo in repos_tags:
                            st.markdown(f":material/package: **{repo.repo_name}**")
                            for tag in repo.tags:
                                st.markdown(f"- {tag}")
                else:
                    st.info("No images found in registry")

    # Push Image section at the bottom
    if img_detail:
        push_image_to_container_registry(col1, img_name, app, dc_reg, img_detail)

PageUtil.set_page_config("Publish to Data Connect", ":material/publish: Publish Base Image to Data Connect")
page_content()
