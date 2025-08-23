import os
import streamlit as st
import pandas as pd
import json

from src.enums import LOCALHOST
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src import os_type
from src.bridge_logs import BridgeLogs, BridgeLogFile, ContentType, LogSourceType
from src.k8s_client import K8sClient, K8sSettings
from src.docker_client import DockerClient, TempLogsSettings
from src.lib.general_helper import FileHelper, StringUtils
from src.lib.usage_logger import USAGE_LOG, UsageMetric
from src.models import AppSettings
from src.os_type import OsType


def archive_older_files(app: AppSettings):
    """  method not currently used
    """
    st.subheader("Archive oldest log files")
    log_folder = os.path.expanduser(app.logs_disk_path) if app.logs_disk_path else ""
    if os.path.exists(log_folder):
        files = BridgeLogs.list_log_files(log_folder, '\.(log|txt|json)$')
        total_file_count = len(files)
        st.write(f"`{total_file_count}` log files in `{app.logs_disk_path}`")
        method = st.radio("archive method", ["by modified date", "group by prefix"])
        if method == "group by prefix":
            st.markdown("Log file counts by prefix:")
            st.markdown(f"All but the newest {BridgeLogs.number_log_files_to_keep} files (by modified date) from each group will be archived")
            groups = BridgeLogs.group_files_by_prefix(files)
            o = ""
            for g, files in groups.items():
                o += f"{g} : {len(files)}\n"
            st.text(o)
            col1, col2 = st.columns(2)
            if col1.button("Confirm Archive"):
                s_logger = StreamLogger(st.container())
                count_archived, archive_path = BridgeLogs.archive_log_files(s_logger, log_folder, groups)
                st.markdown(f"Archived {count_archived} files to {archive_path}")
        else:
            col1, col2 = st.columns(2)
            default = int(total_file_count *.8)
            count_keep = col1.slider('Number of files to keep ', 1, total_file_count, default)
            if col1.button("Confirm Archive"):
                number_to_archive = total_file_count - count_keep
                s_logger = StreamLogger(st.container())
                count_archived, archive_path = BridgeLogs.archive_log_files_by_date(s_logger, log_folder, files, number_to_archive)
                st.markdown(f"Archived {count_archived} files to {archive_path}")
    else:
        st.markdown(f"path '{log_folder}' does not exist")
    if st.columns([1, 3])[1].button("Refresh 🔄"):
        st.session_state.archive_mode = False
        st.rerun()
    st.stop()

def format_filename_win(f: BridgeLogFile):
    return f.name

def format_filename_linux(f: BridgeLogFile):
    return f.format()

# @st.dialog("Change Logs Path", width="large")
# def change_disk_logs_path_dialog(app: AppSettings):
#     st.subheader("Select Logs Folder")
#     form = st.form(key="save_log_folder")
#     selected_folder = form.text_input("Local Logs Folder", app.logs_disk_path).strip()
#     valid_prefixes = app.valid_log_paths_prefixes
#     valid_paths = "".join([f"\n- {p}" for p in valid_prefixes])
#     form.info(f"Logs Folder must start with one of the allowed path prefixes from app_settings.yml:{valid_paths}")
    
#     user_docs = "~/Documents"
#     use_docs_expanded = os.path.expanduser(user_docs)
#     folders_in_documents = list(FileHelper.list_folders(use_docs_expanded))
#     example_folders = [f'\n- {user_docs}/{x}' for x in folders_in_documents]
#     default_local_bridge_logs_path = "~/Documents/My Tableau Bridge Repository (Beta)/Logs"
#     if os.path.exists(os.path.expanduser(default_local_bridge_logs_path)):
#         example_folders.insert(0, "\n- " + default_local_bridge_logs_path)

#     form.info(f"Example valid folders:{''.join(example_folders)}")
#     if form.form_submit_button("Save"):
#         if not any(selected_folder.startswith(p) for p in app.valid_log_paths_prefixes):
#             form.error(f"Path '{selected_folder}' does not start with one of the valid folder prefixes")
#             st.stop()
#         if ".." in selected_folder:
#             form.error(f"'..' characters not allowed")
#             st.stop()
#         selected_folder_full = os.path.expanduser(selected_folder)
#         if not os.path.exists(selected_folder_full):
#             form.error(f"Folder '{selected_folder_full}' does not exist")
#             st.stop()
#         app.logs_disk_path = selected_folder
#         app.save()
#         st.rerun()

@st.dialog("Select Log File", width="large")
def select_log_file_dialog(app: AppSettings):
    icon = LogSourceType.get_source_icon(app.logs_source_type)
    st.markdown(f"### {icon} Select {LogSourceType.get_source_title(app.logs_source_type)} Log")
    with st.container(border=True):
        if app.logs_source_type == LogSourceType.docker:
            _handle_docker_log_selection(app)
        elif app.logs_source_type == LogSourceType.disk:
            _handle_disk_log_selection(app)
        elif app.logs_source_type == LogSourceType.k8s:
            _handle_k8s_log_selection(app)

def _handle_docker_log_selection(app: AppSettings):
    docker_client = DockerClient(StreamLogger(st.container()))
    container_names = docker_client.get_bridge_container_names()
    
    if not container_names:
        st.warning("No local bridge containers found")
        return
        
    selected_container = st.selectbox("Bridge Container", container_names)
    log_filenames = docker_client.list_tableau_container_log_filenames(selected_container)
    
    if not log_filenames:
        st.warning("No logs found in selected container")
        return
        
    log_filenames = [""] + [x for x in log_filenames if x]
    selected_log = st.selectbox("Select Log to view", log_filenames)
    
    if selected_log and st.button("Select", use_container_width=True):
        with st.spinner("Downloading log file..."):
            docker_client.download_single_file_to_disk(selected_container, selected_log)
            app.logs_docker_file = selected_log
            app.logs_docker_container_name = selected_container
            app.save()
            st.rerun()

def _handle_disk_log_selection(app: AppSettings):
    c1,c2 = st.columns([3,1])
    change_folder = False
    if app.logs_disk_path:
        change_folder = c2.checkbox("Change folder")
        ff = os.path.expanduser(app.logs_disk_path)
        if not os.path.exists(ff):
            st.error(f"Folder '{app.logs_disk_path}' does not exist")
            change_folder = True

    if app.logs_disk_path and not change_folder:
        c1.markdown(f"**Current folder:** `{app.logs_disk_path}`")
    else:
        selected_folder = st.text_input("Local Logs Folder", app.logs_disk_path).strip()
        valid_prefixes = app.valid_log_paths_prefixes
        valid_paths = "".join([f"\n- {p}" for p in valid_prefixes])
        st.info(f"Logs Folder must start with one of the allowed path prefixes from app_settings.yml:{valid_paths}")
        
        # Validate and save immediately if changed
        if selected_folder != app.logs_disk_path:
            if not any(selected_folder.startswith(p) for p in app.valid_log_paths_prefixes):
                st.error(f"Path '{selected_folder}' does not start with one of the valid folder prefixes")
                return
            if ".." in selected_folder:
                st.error(f"'..' characters not allowed")
                return
            selected_folder_full = os.path.expanduser(selected_folder)
            if not os.path.exists(selected_folder_full):
                st.error(f"Folder '{selected_folder_full}' does not exist")
                return
            app.logs_disk_path = selected_folder
            app.save()
        
    # File selection section
    ff = os.path.expanduser(app.logs_disk_path)
    if not os.path.exists(ff):
        st.warning(f"Directory '{ff}' does not exist")
        return
        
    result_list = BridgeLogs.list_log_files(ff)
    show_latest = st.checkbox("Filter to latest", value=True)
    
    if show_latest:
        result_list = BridgeLogs.get_latest_per_group(result_list)
        
    format_fun = format_filename_win if os_type.current_os() == OsType.win else format_filename_linux
    sl = st.selectbox(
        f"Select a Log file    count: `{len(result_list)}`",
        result_list,
        format_func=format_fun,
        index=None,
        placeholder="select log file"
    )
    
    # Only show and enable Select button if both folder and file are valid
    button_enabled = bool(app.logs_disk_path and sl)
    if st.button("Select File", disabled=not button_enabled, use_container_width=True):
        app.logs_disk_file = sl.full_path
        app.save()
        st.rerun()

def _handle_k8s_log_selection(app: AppSettings):
    if not K8sSettings.does_kube_config_exist_with_warning(st):
        return
        
    k8s_client = K8sClient()
    pod_names = k8s_client.get_pod_names_by_prefix(app.k8s_namespace, DockerClient.bridge_prefix)
    
    if not pod_names:
        st.warning(f"No bridge pods found in k8s namespace: {app.k8s_namespace}")
        return
        
    selected_pod = st.selectbox("Select k8s Bridge Container", pod_names)
    if selected_pod.startswith("bridge-e2"):
        st.warning(f"Invalid pod {selected_pod}")
        return
        
    log_filenames = cached_k8s_log_file_names(k8s_client, selected_pod, app)
    if not log_filenames:
        st.warning("No logs found in selected pod")
        return
        
    selected_log = st.selectbox("Select Log to view", [""] + log_filenames)
    
    if selected_log and st.button("Select", use_container_width=True):
        with st.spinner("Downloading log file..."):
            k8s_client.download_single_file_to_disk(app.k8s_namespace, selected_pod, selected_log)
            app.logs_k8s_file = selected_log
            app.logs_k8s_pod_name = selected_pod
            app.save()
            st.rerun()

def cached_k8s_log_file_names(k8s_client, selected_pod_name, app: AppSettings):
    status = k8s_client.check_connection()
    if not status.can_connect:
        st.warning(f"Can't connect to kubernetes. {status.error}")
        return []
    log_filenames, error = k8s_client.list_pod_log_filenames(app.k8s_namespace, selected_pod_name)
    if error:
        st.warning(f"Error fetching log file names: {error}")
        return []
    return log_filenames

@st.dialog("Change Log Source Type")
def change_log_source_type_dialog(app: AppSettings):
    st.info("Select the source of the log file you want to analyze. "  
            "\n- Docker logs are from the local bridge container running in Docker.  "
            "\n- Disk logs are from the local bridge logs folder.  "
            "\n- Kubernetes logs are from the bridge pod in your target Kubernetes cluster.")
    options = [LogSourceType.docker, LogSourceType.disk]
    if app.feature_k8s_enabled:
        options.append(LogSourceType.k8s)
    idx = options.index(app.logs_source_type) if app.logs_source_type in options else 0
    log_source = st.radio("Log Source", options, index=idx)
    if st.button("Save", disabled=log_source == app.logs_source_type):
        app.logs_source_type = log_source
        app.save()
        st.rerun()

def refresh_current_log(app: AppSettings):
    """Refresh the currently selected log file"""
    if app.logs_source_type == LogSourceType.docker and app.logs_docker_file:
        with st.spinner("Refreshing docker log..."):
            DockerClient(StreamLogger(st.container())).download_single_file_to_disk(
                app.logs_docker_container_name, 
                app.logs_docker_file
            )
    elif app.logs_source_type == LogSourceType.k8s and app.logs_k8s_file:
        with st.spinner("Refreshing k8s log..."):
            K8sClient().download_single_file_to_disk(
                app.k8s_namespace,
                app.logs_k8s_pod_name,
                app.logs_k8s_file
            )

def display_log_content(target_log: BridgeLogFile):
    """Display the contents of the log file"""
    if not os.path.exists(target_log.full_path):
        st.warning("Selected log file is invalid")
        return
        
    if target_log.content_type != ContentType.json:
        with st.expander("Log Content", expanded=True):
            with open(target_log.full_path, "r") as f:
                content = f.read()
            st.text_area("", content, height=500)
        return
        
    # Load data first
    with st.spinner("Loading log data..."):
        with open(target_log.full_path) as f:
            df = pd.read_json(f, lines=True)
        
        # Remove unnecessary columns
        remove_cols = ['pid', 'tid', 'req', 'sess', 'site', 'user']
        df = df.drop(columns=remove_cols, errors='ignore')
        
    # Handle JSON logs - Filters section
    with st.expander("Filters"):
        col1, col2 = st.columns(2)
        filter_val = str(col2.text_input("Search in Value or Error columns", placeholder="Enter search text..."))
        
        # Setup filters
        unique_k = sorted(df['k'].unique())
        unique_sev = sorted(df['sev'].unique())
        union_sev = ["all"] + list(unique_sev)
        
        sev_val = col1.radio("Severity", union_sev, horizontal=True)
        selected_k = col1.multiselect("Key", unique_k)
        
        # Apply filters
        filtered_df = df
        if sev_val != "all":
            filtered_df = df[df['sev'].str.contains(sev_val, case=False, na=False)]
            
        if selected_k:
            filtered_df = filtered_df[filtered_df['k'].isin(selected_k)]
            
        if filter_val:
            condition2 = filtered_df['v'].astype(str).str.contains(filter_val, case=False, na=False)
            condition3 = filtered_df['e'].astype(str).str.contains(filter_val, case=False, na=False) if 'e' in filtered_df.columns else False
            filtered_df = filtered_df[condition2 | condition3]
    
    # Show filter summary outside the expander
    if any([sev_val != "all", selected_k, filter_val]):
        st.markdown(f"**{len(filtered_df):,}** of **{len(df):,}** entries")
    else:
        st.markdown(f"**{len(df):,}** entries")
    
    # Display results
    filtered_df = filtered_df.iloc[::-1].reset_index(drop=True)
    filtered_df.rename(columns={
        'ts': 'Time',
        'k': 'Key',
        'v': 'Value',
        'sev': 'Severity',
        'e': 'Error'
    }, inplace=True)
    
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        height=700
    )

def show_file_details(target_log: BridgeLogFile, col1: st.columns):
    """Display file size and age details for the given log file"""
    file_stat = os.stat(target_log.full_path)
    file_size_mb = file_stat.st_size / (1024 * 1024)  # Convert to MB
    
    # Get last timestamp from file content for JSON logs
    last_ts = None
    if target_log.content_type == ContentType.json:
        try:
            with open(target_log.full_path, 'rb') as f:
                f.seek(max(0, file_stat.st_size - 4096))
                last_lines = f.read().decode().strip().split('\n')
                last_line = last_lines[-1]
                last_entry = json.loads(last_line)
                if 'ts' in last_entry:
                    last_ts = StringUtils.parse_time_string(last_entry['ts'])
        except Exception as e:
            st.warning(f"Failed to get timestamp from log content: {str(e)}")
            
    details = []
    if last_ts:
        short_ago = StringUtils.short_time_ago(last_ts)
        details.append(f"{short_ago} ago")

    details.append(f"{file_size_mb:.1f} MB")
    col1.caption(" • ".join(details))

def page_content():
    # Header
    ch1, ch2 = st.columns([2,1])
    ch1.markdown("# :material/assignment: Analyze Bridge Logs")
    app = AppSettings.load_static()
    if app.logs_source_type not in [LogSourceType.docker, LogSourceType.disk, LogSourceType.k8s]:
        app.logs_source_type = LogSourceType.docker
        app.save()
    # Select
    ch2.write("")
    ch2.write("")
    source_icon = LogSourceType.get_source_icon(app.logs_source_type)
    log_source_title = LogSourceType.get_source_title(app.logs_source_type)
    if ch2.button(f"{source_icon} {log_source_title}", key="btn_change_source", help="Change the log source to Docker, Disk, or Kubernetes"):
        change_log_source_type_dialog(app)
    if app.logs_source_type == LogSourceType.disk and app.streamlit_server_address != LOCALHOST: #security check. We don't want to allow browsing disk logs from a non-local server
        st.warning(f"Disk logs are only available when streamlit_server_address is {LOCALHOST}")
        return

    # Current log info
    col1, col2 = st.columns([2,1])

    # Get current log info
    target_log = None
    s_con = ""

    if app.logs_source_type == LogSourceType.docker:
        if app.logs_docker_file:
            full_path = str(TempLogsSettings.temp_bridge_logs_path / app.logs_docker_file)
            if os.path.exists(full_path):
                target_log = BridgeLogFile(full_path)
                s_con = f"`{app.logs_docker_container_name}` "
    elif app.logs_source_type == LogSourceType.k8s:
        if app.logs_k8s_file:
            full_path = str(TempLogsSettings.temp_bridge_logs_path / app.logs_k8s_file)
            if os.path.exists(full_path):
                target_log = BridgeLogFile(full_path)
                s_con = f"`{app.logs_k8s_pod_name}` "
    elif app.logs_source_type == LogSourceType.disk:
        if app.logs_disk_file and os.path.exists(app.logs_disk_file):
            target_log = BridgeLogFile(app.logs_disk_file)
            s_con = f"`{app.logs_disk_path}`"
    
    # Display current log info
    if not target_log:
        col1.info(f"No log file selected from {source_icon} {log_source_title}")
    else:
        col1.markdown(f"**{source_icon} {s_con} 📄 `{target_log.name}`**")
        show_file_details(target_log, col1)
        
    # Select Log file
    c1, c2, c3 = col2.columns([3,1,1])
    if c1.button("Select Log File", key="btn_select_file_header"):
        select_log_file_dialog(app)
    if not target_log:
        return
    
    if c2.button("🔄", key="btn_refresh"):
        refresh_current_log(app)
        st.rerun()
    
    # Display log contents
    display_log_content(target_log)

# Initialize page
PageUtil.set_page_config("Logs", PageUtil.NO_PAGE_HEADER)
PageUtil.horizontal_radio_style()
page_content()
