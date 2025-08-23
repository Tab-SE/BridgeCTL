from time import sleep

import streamlit as st

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.shared_bridge_settings import select_image_tags_from_ecr_cache, \
    render_image_cache_refresh_dialog_button, render_image_details
from src.page.ui_lib.stream_logger import StreamLogger
from src.docker_client import DockerClient
from src.ecr_registry_private import EcrRegistryPrivate
from src.models import AppSettings, BridgeImageName


@st.dialog("Remove Image", width="large")
def remove_local_image_dialog(selected_local_image_tag, d_client: DockerClient):
    st.markdown(f"Remove local bridge image `{selected_local_image_tag}` ?")
    if st.button("Confirm Remove Image"):
        with st.spinner(""):
            ret = d_client.remove_image(selected_local_image_tag)
            if ret:
                st.success(f"removed local image {selected_local_image_tag}")
                sleep(3)
                st.rerun()

@st.dialog("Push Image to Container Registry", width="large")
def push_image_to_container_registry_dialog(selected_local_image_name: str, app: AppSettings, d_client: DockerClient):
    st.info("Push image up to AWS ECR Container Registry")
    if st.button("Start Push Image", key = "push_image"):
        cont = st.container(height=390, border=True)
        reg = EcrRegistryPrivate(StreamLogger(cont), app.ecr_private_aws_account_id, app.ecr_private_repository_name, app.aws_region, app.aws_profile)
        is_success, error = reg.check_connection_to_ecr()
        if not is_success:
            st.error(f"Unable to connect to ECR: {error}")
        with st.spinner("pushing image ..."):
            reg.push_image(selected_local_image_name, d_client, False, cont)
            st.success("successfully pushed. Please press the 'Refresh ECR Image Cache' button to see the new image.")
        st.page_link("src/page/52_Publish_Image.py", label="Close")
    else:
        with st.expander("Show script"):
            reg = EcrRegistryPrivate(StreamLogger(st.container()), app.ecr_private_aws_account_id, app.ecr_private_repository_name,
                                     app.aws_region, app.aws_profile)
            _, cmd = reg.push_image(selected_local_image_name, None, True)
            st.code(cmd, language='text')

@st.dialog("Pull Bridge Image from Container Registry", width="large")
def pull_image_from_container_registry_dialog(selected_image_tag: str, app: AppSettings):
    st.info(f"Pull image from AWS ECR Container Registry.")
    st.markdown(f"selected image: `{selected_image_tag}`")
    if st.button("Start Pull Image"):
        with st.spinner(""):
            cont = st.container(height=420, border=True)
            reg = EcrRegistryPrivate(StreamLogger(cont), app.ecr_private_aws_account_id, app.ecr_private_repository_name,
                                     app.aws_region, app.aws_profile)
            reg.pull_image_stream(selected_image_tag, False, cont)
            st.success(f"pulled image")
            st.page_link("src/page/52_Publish_Image.py", label="Close")

def show_local_images(col1, app: AppSettings) -> tuple[str, DockerClient]:
    """Show local Bridge images section and return the selected image name and docker client."""
    with col1.container(border=True):
        st.markdown("### 🐳 Local Bridge Images")
        d_client = DockerClient(StreamLogger(st.container()))
        if not d_client.is_docker_available():
            return None, d_client
        
        tags = d_client.get_tableau_bridge_image_names()
        if not tags:
            st.warning(f"No local docker images found with prefix {BridgeImageName.tableau_bridge_prefix}")
            return None, d_client
            
        tags.insert(0, "")
        selected_local_image_name = st.selectbox("Select Local Image", tags, 
            help="Choose a local Bridge image to push to ECR or view details")
        
        if selected_local_image_name:
            col1a, col1b = st.columns([1,1])
            with col1a:
                if st.button("🚀 Push to ECR →", 
                    disabled=not selected_local_image_name or not app.is_ecr_configured(),
                    use_container_width=True,
                    help="Push the selected image to AWS ECR Container Registry"):
                    push_image_to_container_registry_dialog(selected_local_image_name, app, d_client)
            
            with col1b:
                if st.button("🗑️ Remove Image", 
                    type="secondary",
                    use_container_width=True,
                    help="Delete this image from local Docker"):
                    remove_local_image_dialog(selected_local_image_name, d_client)
        
        return selected_local_image_name, d_client

def page_content():
    app = AppSettings.load_static()
    st.info("""This page allows you to manage and publish Bridge container images between your local Docker environment 
             and AWS ECR Container Registry. You can push local images to ECR or pull remote images to your local Docker.""")
    
    col1, col2 = st.columns(2)
    
    # SECTION - Local Images
    selected_local_image_name, d_client = show_local_images(col1, app)
    
    # SECTION - Remote Images
    with col2.container(border=True):
        st.markdown("### ☁️ Remote ECR Images")
        if not app.is_ecr_configured():
            st.warning("AWS ECR Container Registry not configured. Please configure it in [Settings](/Settings?tab=registry)")
        else:
            selected_image_tag, is_valid = select_image_tags_from_ecr_cache(st, True)
            
            col2a, col2b = st.columns([1,1])
            with col2a:
                if st.button("← 📥 Pull to Docker", 
                    use_container_width=True,
                    help="Pull the selected image from ECR to local Docker"):
                    pull_image_from_container_registry_dialog(selected_image_tag, app)
            
            with col2b:
                render_image_cache_refresh_dialog_button(app, st)
    
    # SECTION - Image Details
    if selected_local_image_name:
        st.markdown("### 📋 Image Details")
        with st.container(border=True):
            render_image_details(st, d_client, selected_local_image_name)


PageUtil.set_page_config("Publish Image", ":material/publish: Publish Bridge Images to Container Registry")
page_content()
