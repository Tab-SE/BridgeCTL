import json
import os
from pathlib import Path
import time

import streamlit as st

from src.bridge_container_builder import bridge_client_config_filename, buildimg_path
from src.bridge_container_runner import BridgeContainerRunner
from src.docker_client import ContainerLabels
from src.docker_client import DockerClient
from src.lib.general_helper import StringUtils
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.page.ui_lib.update_bridge_ui import show_upgrade_dialog, show_scale_up_dialog


@st.dialog("Remove Bridge Container", width="large")
def remove_container_dialog(bridge_container_name: str):
    st.markdown(f"### ⚠️ Remove **{bridge_container_name} ?**")
           
    col1, col2 = st.columns(2)
    if col1.button("Cancel", use_container_width=True):
        st.rerun()
    
    if col2.button("Remove Container", use_container_width=True):
        try:
            logger = StreamLogger(st.container())
            with st.spinner(""):
                is_removed = BridgeContainerRunner.remove_bridge_container_in_docker(logger, bridge_container_name)

            st.success(f"Removed successfully")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to remove container: {str(e)}")

def btn_stout_logs(container_name):
    st.markdown(f"#### :material/web_stories: {container_name}")

    # st.markdown(f"Logs for **{container_name}**")
    logic = DockerClient(StreamLogger(st.container()))
    stdout_logs = logic.get_stdout_logs(container_name)
    cont = st.container(height=500)
    cont.markdown(f"""```
{stdout_logs}
```""")

@st.dialog("Edit Bridge Client Configuration", width="large")
def edit_bridge_client_configuration(container_name):
    st.info("Fine tune the behavior of Tableau bridge by editing client configuration parameters " 
        f" stored in `{bridge_client_config_filename}`")
    st.markdown(f"target bridge container: `{container_name}`")
    col1,col2 = st.columns([3,1])
    col1.markdown("Current client configuration:")
    client = DockerClient(StreamLogger(st.container()))
    local_scratch_path = client.download_single_file_to_disk(container_name, bridge_client_config_filename, True)
    with open(local_scratch_path, "r") as f:
        content = f.read()
    is_edit = False #col2.checkbox("edit")
    if is_edit:
        edited = st.text_area("Client config", content, height=400)
    else:
        cont = st.container(height=400)
        cont.code(content, language="json")
    client_config  = json.loads(content)

    with st.form(key="edit_config"):
        current_connectionPool = client_config["serviceConnectionSettings"]["connectionPool"]["size"]
        selected_connectionPool = st.number_input("connectionPool", value= current_connectionPool, key = "connection_pool", min_value=1, max_value=100)
        current_maxRemoteJobConcurrency = client_config["dataSourceRefreshSettings"]["maxRemoteJobConcurrency"]
        selected_maxRemoteJobConcurrency = st.number_input("maxRemoteJobConcurrency", value =current_maxRemoteJobConcurrency, key="job_concurrency", min_value=1, max_value=100)
        current_jsonLogForExtractRefresh = client_config["dataSourceRefreshSettings"]["JSONLogForExtractRefresh"]
        idx = 1 if current_jsonLogForExtractRefresh == True else 0
        selected_jsonLogForExtractRefresh = (st.selectbox("JSONLogForExtractRefresh", ["false", "true"], idx, key="extract_logs") == "true")
        save_as_default = st.checkbox("save as default for new containers")
        if st.form_submit_button("Update Client Configuration"):
            no_op = (current_connectionPool == selected_connectionPool
                       and current_maxRemoteJobConcurrency == selected_maxRemoteJobConcurrency
                       and current_jsonLogForExtractRefresh == selected_jsonLogForExtractRefresh)
            if selected_connectionPool < selected_maxRemoteJobConcurrency:
                st.warning("connectionPool should be greater than or equal to maxRemoteJobConcurrency")
                return
            client_config["serviceConnectionSettings"]["connectionPool"]["size"] = selected_connectionPool
            client_config["dataSourceRefreshSettings"]["maxRemoteJobConcurrency"] = selected_maxRemoteJobConcurrency
            client_config["dataSourceRefreshSettings"]["JSONLogForExtractRefresh"] = selected_jsonLogForExtractRefresh
            if save_as_default:
                target = Path(buildimg_path) / bridge_client_config_filename
                with target.open("w") as f:
                    json.dump(client_config, f, indent=4)
                st.success("saved as default for future new containers")
            if no_op:
                st.warning("No changes detected")
                return
            is_success, out = client.edit_client_config_v2(container_name, client_config)
            st.text(out)
            if is_success:
                st.success(f"updated config for `{container_name}`")
                st.markdown("restarting container to apply changes")
                with st.spinner(""):
                    client.restart_container(container_name)
                    st.success("restart success")
            else:
                st.error(f"Error updating client configuration")

    if st.columns(2)[1].button("remove default"):
        target = Path(buildimg_path) / bridge_client_config_filename
        if target.exists():
            os.remove(target)
            st.success(f"removed default client configuration `{target}`")
        else:
            st.info(f"no default client configuration found at `{target}`")

def btn_zip_logs(container_name):
    st.markdown(f"zipped Logs for **{container_name}**")
    docker_client = DockerClient(StreamLogger(st.container()))
    zipf = docker_client.get_all_bridge_logs_as_tar(container_name)
    if not zipf:
        return
    with open(zipf, "rb") as f:
        st.download_button("Download Logs in TarGzip", f, file_name=f"bridge-logs-{container_name}.tgz")
    os.remove(zipf)

def restart_container(container_name):
    st.markdown(f"restarting container: `{container_name}`")
    docker_client = DockerClient(StreamLogger(st.container()))
    docker_client.restart_container(container_name)
    st.success(f"restarted container: `{container_name}`")

def btn_detail(container_name):
    st.write("")
    st.write("")
    st.markdown(f"#### :material/info: {container_name}")
    logic = DockerClient(StreamLogger(st.container()))
    details = logic.get_container_details(container_name, True)
    col1, col2 = st.columns(2)
    col1.markdown(f"image name: `{details.image_name}`")
    col2.markdown(f"created: `{StringUtils.short_time_ago(details.image_create_date)}` ago")
    str_labels = ""
    for a in dir(ContainerLabels):
        if not a.startswith("__"):
            value = details.labels.get(a)
            str_labels += f"- {a}: `{value}`\n"
    st.markdown(f"container status: `{details.status}, started {details.started_ago} ago`")
    st.markdown("Labels: ")
    st.markdown(str_labels)
    c1,c2,c3 = st.columns(3)
    c1.metric("cpu", f"{details.cpu_usage_pct:.2f}%")
    c2.metric("mem", f"{details.mem_usage_mb:.2f}Mb")
    c3.metric("disk", details.disk_usage)
    st.markdown(f"JDBC Drivers: `{details.jdbc_drivers}`", help="list `.jar` files found in /opt/tableau/tableau_driver/jdbc")
    st.markdown(f"ODBC Drivers: `{details.odbc_drivers}`", help="ODBC entries returned by `odbcinst -q -d`")
    if details.network_mode:
        st.markdown(f"Network Mode: `{details.network_mode}`")
    if details.volume_mounts:
        st.markdown("Volume Mounts:")
        for vm in details.volume_mounts:
            st.markdown(f"  - `{vm}`")

def show_running_dockers():
    col1, col2 = st.columns([1,1])
    col1.markdown("### Local Bridge Containers")
    st.markdown("---")
    col2a,col2b = col2.columns([1,2])
    if col2a.button(":material/handyman: Update Image", key="update_image", use_container_width=True):
        show_upgrade_dialog()
    if col2b.button(":material/trending_up: Scale Up", key="scale_up", use_container_width=True):
        show_scale_up_dialog()

    cont1 = st.container()

    with st.spinner(""):
        docker_client = DockerClient(StreamLogger(st.container()))
        if not docker_client.is_docker_available():
            return
        containers = docker_client.get_containers_list(DockerClient.bridge_prefix)
        if not containers:
            st.info("🔍 No local bridge containers found. Use the Run Bridge Container page to start one.")
            return

        for idx, c in enumerate(containers):
            cont = cont1.container()
            cols = cont.columns([2, 2, 1, 1, 2])
            
            # Container name and status with site/pool info
            status_icon = "🟢" if c.status == "running" else "🔴"
            cols[0].markdown(f"**🐳 {c.name}**")
            
            # Get container details for labels
            details = docker_client.get_container_details(c.name, False)
            site_name = details.labels.get(ContainerLabels.tableau_sitename, "")
            pool_name = details.labels.get(ContainerLabels.tableau_pool_name, "")
            status_text = f"{status_icon} {c.status}"
            if site_name or pool_name:
                status_text += f" 🌐 {site_name}"
                if pool_name:
                    status_text += f" · {pool_name}"
            cols[1].markdown(status_text)
            
            # Action buttons with consistent widths
            if cols[2].button(":material/info: Detail", key=f"detail_{idx}", use_container_width=True):
                btn_detail(c.name)
            if cols[3].button(":material/web_stories: Log", key=f"logs_{idx}", use_container_width=True, help="Stdout logs"):
                btn_stout_logs(c.name)
            
            # Group additional actions in expander
            with cols[4].expander("More Actions"):
                col1, col2 = st.columns(2)
                if col1.button(":material/delete: Remove", key=f"rm_{idx}", use_container_width=True):
                    remove_container_dialog(c.name)
                if col2.button(":material/settings: Config", key=f"config_{idx}", use_container_width=True):
                    edit_bridge_client_configuration(c.name)
                col1, col2 = st.columns(2)
                if col1.button(":material/folder_zip: Zip Logs", key=f"zip_{idx}", use_container_width=True, help="Collect all bridge logs and download as a zip file"):
                    btn_zip_logs(c.name)
                if col2.button(":material/refresh: Restart", key=f"restart_{idx}", use_container_width=True):
                    restart_container(c.name)
            
            cont.markdown("---")

    st.markdown("")
    st.markdown("")

def page_content():
    with st.expander("ℹ️ Instructions", expanded=False):
        st.info("""
            Manage your Tableau Bridge containers running in Docker:
            - View container status, details and docker logs
            - Edit bridge client configuration
            - Collect and download bridge log files
            - Remove containers that are no longer needed
        """)
    show_running_dockers()
    if st.columns([3,1])[1].button("🔄"):
        st.rerun()
    st.markdown("")
    st.markdown("")

PageUtil.set_page_config("Manage Bridge", ":material/list: Manage Tableau Bridge Containers in Local Docker")
page_content()
