from time import sleep

import streamlit as st

from src.docker_client import DockerClient, ContainerLabels
from src.k8s_client import K8sClient
from src.models import AppSettings
from src.page.ui_lib.page_util import PageUtil


@st.dialog("Remove Pod", width="large")
def remove_pod_dialog(pod_name: str, namespace: str):
    st.markdown(f"### ⚠️ Remove Pod **{pod_name}**?")
    st.info(f"This will delete the pod from namespace `{namespace}`")
           
    col1, col2 = st.columns(2)
    if col1.button("Cancel", use_container_width=True):
        st.rerun()
    
    if col2.button("Remove Pod", use_container_width=True, type="primary"):
        try:
            k8s_client = K8sClient()
            with st.spinner("Removing pod..."):
                k8s_client.delete_pod(namespace, pod_name)
            st.success("✓ Pod removed successfully")
            sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to remove pod: {str(e)}")


def show_pod_logs(pod_name: str, namespace: str):
    st.markdown(f"#### :material/web_stories: {pod_name}")
    
    k8s_client = K8sClient()
    logs = k8s_client.get_stdout_pod_logs(namespace, pod_name)
    cont = st.container(height=500)
    cont.markdown(f"""```
{logs}
```""")


def show_pod_details(pod_name: str, namespace: str):
    st.markdown(f"#### :material/info: {pod_name}")
    k8s_client = K8sClient()
    detail = k8s_client.get_pod_detail(namespace, DockerClient.bridge_prefix, pod_name)
    if not detail:
        st.error(f"Pod {pod_name} not found")
        return
    col1, col2 = st.columns(2)
    col1.markdown(f"Created: `{detail.created_ago}`")
    col2.markdown(f"Started: `{detail.started_ago}`")
    st.markdown("**Labels:**\n")
    for k, v in detail.labels.items():
        st.markdown(f"- {k}: `{v}`")
    st.markdown(f"**Image:** `{detail.image_url}`")


def show_running_pods():
    col1, col2 = st.columns([1,1])
    col1.markdown("### Kubernetes Bridge Pods")
    st.markdown("---")

    app = AppSettings.load_static()
    k8s_client = K8sClient()
    
    # Get pods with our prefix in the configured namespace
    pods = k8s_client.get_pods_by_prefix(app.k8s_namespace, DockerClient.bridge_prefix)
    
    if not pods:
        st.info("🔍 No bridge pods found in namespace. Use the Deploy Bridge to Kubernetes page to start one.")
        return

    for idx, pod in enumerate(pods):
        cont = st.container()
        cols = cont.columns([2, 2, 1, 1, 1])
        status_icon = "🟢" if pod.phase == "Running" else "🔴"
        cols[0].markdown(f"📦 **{pod.name}**")
        site_name = pod.labels.get(ContainerLabels.tableau_sitename, "")
        pool_name = pod.labels.get(ContainerLabels.tableau_pool_name, "")
        status_text = f"{status_icon} {pod.phase}"
        if site_name or pool_name:
            status_text += f" 🌐 {site_name}"
            if pool_name:
                status_text += f" · {pool_name}"
        cols[1].markdown(status_text)
        # Action buttons
        if cols[2].button(":material/info: Detail", key=f"detail_{idx}", use_container_width=True):
            show_pod_details(pod.name, app.k8s_namespace)
        if cols[3].button(":material/web_stories: Logs", key=f"logs_{idx}", use_container_width=True):
            show_pod_logs(pod.name, app.k8s_namespace)
        if cols[4].button(":material/delete: Remove", key=f"remove_{idx}", use_container_width=True):
            remove_pod_dialog(pod.name, app.k8s_namespace)
        cont.markdown("---")


def page_content():
    with st.expander("ℹ️ Instructions", expanded=False):
        st.info("""
            Manage your Tableau Bridge pods running in Kubernetes:
            - View pod status and container logs
            - Remove pods that are no longer needed
            - Check pod configurations and labels
        """)
    
    show_running_pods()
    
    if st.columns([3,1])[1].button("🔄"):
        st.rerun()


PageUtil.set_page_config("Manage K8s Bridge", ":material/format_list_bulleted:  Manage Tableau Bridge Pods in Kubernetes")
page_content()
