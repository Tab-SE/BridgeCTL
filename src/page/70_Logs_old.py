# import os
# import streamlit as st
# import pandas as pd

# from src.page.ui_lib.page_util import PageUtil
# from src.page.ui_lib.stream_logger import StreamLogger
# from src import os_type
# from src.bridge_logs import BridgeLogs, BridgeLogFile, ContentType, LogSourceType
# from src.k8s_client import K8sClient, K8sSettings
# from src.docker_client import DockerClient, TempLogsSettings
# from src.lib.general_helper import FileHelper
# from src.lib.usage_logger import USAGE_LOG, UsageMetric
# from src.models import AppSettings
# from src.os_type import OsType


# def archive_older_files(app: AppSettings):
#     """  method not currently used
#     """
#     st.subheader("Archive oldest log files")
#     log_folder = os.path.expanduser(app.logs_disk_path) if app.logs_disk_path else ""
#     if os.path.exists(log_folder):
#         files = BridgeLogs.list_log_files(log_folder, '\.(log|txt|json)$')
#         total_file_count = len(files)
#         st.write(f"`{total_file_count}` log files in `{app.logs_disk_path}`")
#         method = st.radio("archive method", ["by modified date", "group by prefix"])
#         if method == "group by prefix":
#             st.markdown("Log file counts by prefix:")
#             st.markdown(f"All but the newest {BridgeLogs.number_log_files_to_keep} files (by modified date) from each group will be archived")
#             groups = BridgeLogs.group_files_by_prefix(files)
#             o = ""
#             for g, files in groups.items():
#                 o += f"{g} : {len(files)}\n"
#             st.text(o)
#             col1, col2 = st.columns(2)
#             if col1.button("Confirm Archive"):
#                 s_logger = StreamLogger(st.container())
#                 count_archived, archive_path = BridgeLogs.archive_log_files(s_logger, log_folder, groups)
#                 st.markdown(f"Archived {count_archived} files to {archive_path}")
#         else:
#             col1, col2 = st.columns(2)
#             default = int(total_file_count *.8)
#             count_keep = col1.slider('Number of files to keep ', 1, total_file_count, default)
#             if col1.button("Confirm Archive"):
#                 number_to_archive = total_file_count - count_keep
#                 s_logger = StreamLogger(st.container())
#                 count_archived, archive_path = BridgeLogs.archive_log_files_by_date(s_logger, log_folder, files, number_to_archive)
#                 st.markdown(f"Archived {count_archived} files to {archive_path}")
#     else:
#         st.markdown(f"path '{log_folder}' does not exist")
#     if st.columns([1, 3])[1].button("Refresh 🔄"):
#         st.session_state.archive_mode = False
#         st.rerun()
#     st.stop()

# def change_logs_path(app: AppSettings):
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
#         found = False
#         for p in app.valid_log_paths_prefixes:
#             if selected_folder.startswith(p):
#                 found = True
#                 break
#         if not found:
#             form.error(f"Path '{selected_folder}' does not start with one of the valid folder prefixes")
#             st.stop()
#         if ".." in selected_folder:
#             form.error(f"'..' characters not allowed")
#             st.stop()
#         selected_folder_full = os.path.expanduser(selected_folder)
#         form.markdown(f"`{selected_folder_full}`")
#         if not os.path.exists(selected_folder_full):
#             form.error(f"Folder '{selected_folder_full}' does not exist")
#             st.stop()
#         app.logs_disk_path = selected_folder
#         app.save()
#         st.rerun()
#     st.stop()

# def format_filename_win(f: BridgeLogFile):
#     return f.name # for some reason on windows f.format() doesn't work (need to test more about why)

# def format_filename_linux(f: BridgeLogFile):
#     return f.format()

# def render_change_source_button(cont_change_source):
#     pass
#     # cont_change_source.button("Change Source", on_click=remove_log_source_type)

# def select_docker_logfile(app: AppSettings, refresh: bool, cont_change_source) -> (BridgeLogFile, str):
#     full_path = str(TempLogsSettings.temp_bridge_logs_path / app.logs_docker_file) if (TempLogsSettings.temp_bridge_logs_path and app.logs_docker_file) else ""

#     if os.path.exists(full_path):
#         if refresh:
#             DockerClient(StreamLogger(st.container())).download_single_file_to_disk(app.logs_docker_container_name, app.logs_docker_file)
#         return BridgeLogFile(full_path), app.logs_docker_container_name
#     else:
#         render_change_source_button(cont_change_source)
#         docker_client = DockerClient(StreamLogger(st.container()))
#         container_names = docker_client.get_bridge_container_names()
#         if not container_names:
#             st.write("No local bridge containers")
#             st.stop()

#         selected_container_name = st.selectbox("Select Container", container_names)
#         # st.markdown(f"Logs for docker container **{selected_container_name}**", unsafe_allow_html=True) #{BridgeContainerLogsPath.get_logs_path()

#         log_filenames = docker_client.list_tableau_container_log_filenames(selected_container_name)
#         if log_filenames:
#             log_filenames = [x for x in log_filenames if x]  # remove empty strings
#         if not log_filenames:
#             st.markdown(f"No logs found")
#             st.stop()

#         log_filenames.insert(0, "")
#         selected_log = st.selectbox("Select Log to view", log_filenames)
#         if not selected_log:
#             st.warning(f"No log selected")
#             st.stop()
#         docker_client.download_single_file_to_disk(selected_container_name, selected_log)
#         app.logs_docker_file = selected_log
#         app.logs_docker_container_name = selected_container_name
#         app.save()
#         st.rerun()

# # @st.cache_data(show_spinner="fetching list of log file names from k8s pod", ttl=1800) # 30 mins
# def cached_k8s_log_file_names(k8s_client, selected_pod_name, app: AppSettings):
#     status = k8s_client.check_connection()
#     if not status.can_connect:
#         st.warning(f"Can't connect to kubernetes. {status.error}")
#         return []
#     log_filenames, error = k8s_client.list_pod_log_filenames(app.k8s_namespace, selected_pod_name)
#     if error:
#         st.warning(f"Error fetching log file names: {error}")
#         return []
#     return log_filenames

# # @st.cache_data
# def get_k8s_pod_names(k8s_client):
#     return []

# def select_k8s_logfile(app: AppSettings, refresh: bool, cont_change_source) -> (BridgeLogFile, str):
#     K8sSettings.does_kube_config_exist_with_warning(st)
#     full_path = str(TempLogsSettings.temp_bridge_logs_path / app.logs_k8s_file) if (TempLogsSettings.temp_bridge_logs_path and app.logs_k8s_file) else ""
#     if os.path.exists(full_path):
#         if refresh:
#             with st.spinner("Re-Downloading log file"):
#                 K8sClient().download_single_file_to_disk(app.k8s_namespace, app.logs_k8s_pod_name, app.logs_k8s_file)
#         return BridgeLogFile(full_path), app.logs_k8s_pod_name
#     else:
#         render_change_source_button(cont_change_source)
#         k8s_client = K8sClient()
#         pod_names = k8s_client.get_pod_names_by_prefix(app.k8s_namespace, DockerClient.bridge_prefix)
#         if not pod_names:
#             st.write(f"No bridge pods in k8s namespace: {app.k8s_namespace}")
#             st.stop()
#         selected_pod_name = st.selectbox("Select k8s Bridge Container", pod_names)
#         if selected_pod_name.startswith("bridge-e2"): #FutureDev: fix to look at bridge status.
#             st.write(f"invalid pod {selected_pod_name}")
#             st.stop()
#         log_filenames = cached_k8s_log_file_names(k8s_client, selected_pod_name, app)# k8s_client.list_pod_log_filenames(K8sSettings.TABLEAU_NAMESPACE, selected_pod_name)

#         st.markdown(f"Logs for pod **{selected_pod_name}**")
#         if not log_filenames:
#             st.markdown(f"No logs found")
#             st.stop()
#         log_filenames.insert(0, "")
#         selected_log = st.selectbox("Select Log to view", log_filenames)
#         if not selected_log:
#             st.warning(f"No log selected")
#             st.stop()
#         with st.spinner("Downloading log file"):
#             app.logs_k8s_file = selected_log
#             app.logs_k8s_pod_name = selected_pod_name
#             app.save()
#             full_path = TempLogsSettings.temp_bridge_logs_path / selected_log
#             if not full_path.exists(): #FutureDev: perhaps remove this and always download.
#                 k8s_client.download_single_file_to_disk(app.k8s_namespace, selected_pod_name, selected_log)
#             st.rerun()


# def remove_log_source_type():
#     app = AppSettings()
#     app.load()
#     app.logs_source_type = None
#     app.save()

# def get_log_source_type(app: AppSettings):
#     options = [LogSourceType.docker, LogSourceType.disk]
#     if app.feature_k8s_enabled:
#         options.append(LogSourceType.k8s)
#     idx = options.index(app.logs_source_type) if app.logs_source_type in options else 0
#     log_source_type = st.radio(" ", options, index=idx)
#     if log_source_type != app.logs_source_type:
#         app.logs_source_type = log_source_type
#         app.save()
#     return log_source_type

# def select_log_file(app: AppSettings, refresh: bool, cont_change_source) -> (BridgeLogFile, str, str): # return BridgeLogFile,  log_source_type, selected_container_name
#     log_source_type = app.logs_source_type

#     if log_source_type == LogSourceType.disk:
#         if os.path.exists(str(app.logs_disk_file)):
#             return BridgeLogFile(app.logs_disk_file), LogSourceType.disk, None
#         else:
#             render_change_source_button(cont_change_source)
#             if app.logs_disk_path:
#                 selected_folder = os.path.expanduser(app.logs_disk_path)
#             else:
#                 change_logs_path(app)
#                 st.stop()
#             st.subheader("Select Log File")
#             if os.path.exists(selected_folder):
#                 result_list = BridgeLogs.list_log_files(selected_folder)
#                 cont1 = st.container()
#                 show_latest = cont1.checkbox("filter to latest", value=True)
#                 if st.button("change folder"):
#                     app.logs_disk_file = ""
#                     app.logs_disk_path = ""
#                     app.save()
#                     st.rerun()
#                 if st.button("archive oldest log files"):
#                     st.session_state.archive_mode = True
#                     st.rerun()

#                 if show_latest:
#                     result_list = BridgeLogs.get_latest_per_group(result_list)
#                 format_fun = format_filename_win if os_type.current_os() == OsType.win else format_filename_linux
#                 sl = cont1.selectbox(f"Select a Log file from `{app.logs_disk_path}`    count: `{len(result_list)}`", result_list,
#                                      format_func= format_fun, index= None, placeholder= "select log file")
#                 if not sl:
#                     st.stop()
#                 app.logs_disk_file = sl.full_path
#                 app.save()
#                 st.rerun()
#             else:
#                 st.warning(f"Directory '{selected_folder}' does not exist\n\n"
#                            f"please select a valid Logs folder")
#                 change_logs_path(app)
#                 st.stop()
#     if log_source_type == LogSourceType.docker:
#         bfile, container_name = select_docker_logfile(app, refresh, cont_change_source)
#         return bfile, log_source_type, container_name
#     elif log_source_type == LogSourceType.k8s:
#         bfile, container_name = select_k8s_logfile(app, refresh, cont_change_source)
#         return bfile, log_source_type, container_name
#     else:
#         raise ValueError(f"Invalid log source: {log_source_type}")


# def page_content():
#     # PageUtil.horizontal_radio_style()
#     app = AppSettings()
#     app.load()
#     if st.session_state.archive_mode:
#         archive_older_files(app)
#     cont_change_source = get_log_source_type(app)
#     target_log, log_source_type, selected_container_name = select_log_file(app, False, cont_change_source)

#     col1, col2 = st.columns(2)
#     if log_source_type == LogSourceType.docker:
#         s_con = f" Container: `{selected_container_name}`"
#     elif log_source_type == LogSourceType.k8s:
#         s_con = f" Pod: `{selected_container_name}`"
#     else:
#         s_con = ""
#     col1.markdown(f"Log file: `{target_log.name}`{s_con}") # ({target_log.source_type})")
#     c1, c2, c3 = col2.columns([3,1,1])
#     if c1.button("Select Log File"):
#         if log_source_type == LogSourceType.disk:
#             app.logs_disk_file = None
#         elif log_source_type == LogSourceType.docker:
#             app.logs_docker_file = None
#             app.logs_docker_container_name = None
#         elif log_source_type == LogSourceType.k8s:
#             app.logs_k8s_file = None
#             app.logs_k8s_pod_name = None
#         app.save()
#         USAGE_LOG.log_usage(UsageMetric.logs_select_file)
#         st.rerun()

#     if c2.button("🔄&nbsp;&nbsp;Refresh"):
#         target_log, log_source_type, selected_container_name = select_log_file(app, True, cont_change_source)
#     # with open(target_log.full_path, "rb") as f:
#     #     c3.download_button("⬇️&nbsp;&nbsp;Download", f, file_name=target_log.name)

#     if not os.path.exists(target_log.full_path):
#         st.warning(f"Selected log file is invalid")
#         st.stop()

#     if target_log.content_type != ContentType.json:
#         with open(target_log.full_path, "r") as f:
#             content = f.read()
#         st.text_area("Log Content", content, height=500) #, label_visibility="collapsed")
#         st.stop()

#     col1, col2 = st.columns(2)
#     filter_val = str(col2.text_input("search for text in columns: Value or Error"))
#     with st.spinner():
#         with open(target_log.full_path) as f:
#             df = pd.read_json(f, lines=True) #, dtype=np.int64)
#         remove_cols = ['pid', 'tid', 'req', 'sess', 'site', 'user'] #Drop columns only if they are found in the df
#         df = df.drop(columns=remove_cols, errors='ignore')
#         unique_k = df['k'].unique()
#         unique_sev = df['sev'].unique()
#         union_sev = ["all"] + list(unique_sev)
#         sev_val = col1.radio("Severity", union_sev)
#         selected_k = col1.multiselect("Key", unique_k)
#         # fav = col2.selectbox("Favorite filters", ["1", "2", "3"])
#         c1, c2 = st.columns(2)
#         if sev_val == "all":
#             filtered_df = df
#         else:
#             filtered_df = df[df['sev'].str.contains(sev_val, case=False, na=False)]
#         if sev_val != "all":
#             c1.markdown(f"filter: `sev = {sev_val}`")
#         if selected_k:
#             c1.markdown(f"filter: `k in {selected_k}`")
#             filtered_df = filtered_df[filtered_df['k'].isin(selected_k)]
#         if filter_val:
#             c1.markdown(f"filter: `value or error columns contain '{filter_val}'`")
#             condition2 = filtered_df['v'].astype(str).str.contains(filter_val, case=False, na=False)
#             if 'e' in filtered_df.columns:
#                 condition3 = filtered_df['e'].astype(str).str.contains(filter_val, case=False, na=False)
#             else:
#                 condition3 = False
#             filtered_df = filtered_df[condition2 | condition3]
#         c2.markdown(f"rows: *{len(filtered_df):,}*") #    &nbsp;&nbsp;&nbsp;&nbsp;  default sort: Time descending") #, log file size: {target_log.size}")
#         filtered_df = filtered_df.iloc[::-1].reset_index(drop=True)
#         filtered_df.rename(columns={'ts':'Time', 'k': 'Key', 'v': 'Value', 'sev': 'Severity', 'e': 'Error'}, inplace=True)
#         st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=700)


# def default_session_state():
#     if "archive_mode" not in st.session_state:
#         st.session_state.archive_mode = False


# PageUtil.set_page_config("Logs", ":material/assignment: Analyze Bridge Logs")
# default_session_state()
# PageUtil.horizontal_radio_style()
# page_content()
