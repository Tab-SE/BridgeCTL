import streamlit as st

from src.enums import ImageRegistryType
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.shared_bridge_settings import load_and_select_tokens, \
    show_k8s_context, bridge_settings_view_mode_content, show_and_select_image_tags
from src.page.ui_lib.stream_logger import StreamLogger
from src import bridge_settings_file_util
from src.docker_client import DockerClient
from src.k8s_bridge_manager import K8sBridgeManager
from src.k8s_client import K8sSettings, K8sClient
from src.models import AppSettings


def page_content():
    # st.markdown("# :material/kubernetes: Deploy Bridge to Kubernetes")
    
    # Instructions in an expandable section
    with st.expander("ℹ️ Instructions", expanded=False):
        st.info(
            "To deploy bridge container images to kubernetes:\n"
            "1. Configure your kubernetes cluster in [Settings](/Settings?tab=k8s)\n"
            "2. Select a container image (build locally or from registry)\n"
            "3. Choose Personal Access Tokens (PAT) for the bridge agents\n"
            "4. Click Deploy to create the pods"
        )

    # Configuration Status Section
    status_container = st.container(border=True)
    # status_container.markdown("### Configuration Status")
    
    col1, col2 = status_container.columns(2)
    
    # Kubernetes Context
    with col1:
        # st.markdown("#### 🎯 Kubernetes Context")
        if not show_k8s_context(st.container()):
            return
        if not K8sSettings.does_kube_config_exist_with_warning(st):
            return
    
    # Bridge Settings
    with col2:
        st.markdown("#### ⚙️ Target Bridge Pool")
        bridge_settings_view_mode_content()

    st.markdown("##### 🐳 Container Image")
    app = AppSettings.load_static()
    tag_is_valid = show_and_select_image_tags(st, app)
    if not tag_is_valid:
        st.warning("Please select a container image")
        return
        
    # Kubernetes Connection Check
    k8s_client = K8sClient()
    status = k8s_client.check_connection()
    if not status.can_connect:
        st.error(f"Cannot connect to kubernetes: {status.error}")
        return
    
    # Token Selection
    pod_names = k8s_client.get_pod_names_by_prefix(app.k8s_namespace, DockerClient.bridge_prefix)
    pod_names2 = [p.replace("-","_",2) for p in pod_names]
    selected_token_names, token_loader, tokens = load_and_select_tokens(st, pod_names2, False)

    if st.button("Run Bridge Pods", disabled=not selected_token_names):
        with st.spinner("Deploying pods..."):
            start_bridge_pods(selected_token_names, app)
        if st.button("🔄"):
            st.rerun()


def start_bridge_pods(token_names, app: AppSettings):
    req = bridge_settings_file_util.load_settings()
    mgr = K8sBridgeManager(StreamLogger(st.container()), req, app)

    # Set image pull policy based on registry selection
    image_pull_policy = "Never" if app.img_registry_type == ImageRegistryType.local_docker else "Always"
    image_tag = app.selected_remote_image_tag if app.img_registry_type == ImageRegistryType.aws_ecr else app.selected_image_tag
    st.write(f"image_tag: {image_tag}")
    for token_name in token_names:
        friendly_error = mgr.run_bridge_container_in_k8s(
            token_name,
            image_tag,
            image_pull_policy=image_pull_policy
        )
        if friendly_error:
            st.warning(friendly_error)
        else:
            st.success(f"✓ Pod {token_name} deployed successfully")


PageUtil.set_page_config("Run Bridge Pods in K8s", ":material/directions_run: Run Bridge Pods in Kubernetes", True)
PageUtil.horizontal_radio_style()
page_content()
