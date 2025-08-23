import streamlit as st

from src.page.ui_lib.login_manager import LoginManager
from src.token_loader import TokenLoaderMigrate
from src.cli.app_config import APP_CONFIG
from src.models import AppSettings, APP_STATE

pages = {}
app = AppSettings.load_static()


if LoginManager.check_login(app):
    pages[""] = [
        st.Page("src/page/1_Home.py", icon=":material/home:"),
        st.Page("src/page/5_Settings.py", icon=":material/settings:"),
    ]
    pages["Run"] =[
        st.Page("src/page/10_Build_Bridge.py", icon=":material/build:"),
        st.Page("src/page/20_Run_Bridge.py", icon=":material/directions_run:"),
        st.Page("src/page/50_Manage_Bridge.py", icon=":material/list:"),
    ]
    if app.feature_aws_ecr_enabled:
        pages["Run"].append(st.Page("src/page/52_Publish_Image.py", icon=":material/publish:"))
    if app.feature_example_scripts_enabled:
        pages["Run"].append(st.Page("src/page/90_Example_Scripts.py", icon=":material/code:"))

    if app.dataconnect_feature_enable:
        pages["Data Connect"] = [
            st.Page("src/page/55_Publish_Base_Image.py", icon=":material/publish:"),
        ]
    tm = "Health Monitor 🟢" if app.monitor_enable_monitoring else "Health Monitor ⚪"
    pages["Monitor"] = [
        st.Page("src/page/60_Status.py", icon=":material/monitor_heart:"),
        st.Page("src/page/91_Health_Monitor.py", icon=":material/monitoring:", title=tm),
        st.Page("src/page/81_Jobs.py", icon=":material/work:"),
        st.Page("src/page/80_Test_Bridge.py", icon=":material/labs:"),
        st.Page("src/page/70_Logs.py", icon=":material/assignment:"),
        # st.Page("src/page/71_Logs_(Beta).py", icon=":material/assignment:"),
    ]

    if app.feature_k8s_enabled:
        pages["Kubernetes"] = [
            st.Page("src/page/110_k8s_Run_Bridge.py", icon=":material/directions_run:"),
            st.Page("src/page/115_k8s_Manage_Bridge.py", icon=":material/format_list_bulleted:"),
        ]
        if app.autoscale_show_page:
            pages["Kubernetes"].append(st.Page("src/page/117_k8s_Auto_Scale.py", icon=":material/unfold_more:"))

    if APP_CONFIG.is_internal_build():
        if app.feature_hammerhead_enabled:
            pages["Hammerhead"] = [
                st.Page("src/internal/warhammer/page/119_Hammerhead_-_Auth.py", icon=":material/key:"),
                st.Page("src/internal/warhammer/page/125_Hammerhead_-_Report.py", icon=":material/signal_cellular_alt:"),
                st.Page("src/internal/warhammer/page/126_Hammerhead_-_Create.py", icon=":material/add_circle:"),
                st.Page("src/internal/warhammer/page/129_Hammerhead_-_Modify.py", icon=":material/play_arrow:"),
            ]
        if app.feature_enable_edge_network_page:
            pages["Edge"] = [
                st.Page("src/internal/gw_client/200_Edge_Network.py", icon=":material/account_tree:"),
                st.Page("src/internal/gw_client/201_RemoteCommands.py", icon=":material/monitoring:"),
            ]
    if app.feature_enable_chat_with_tableau:
        pages["Tableau Langchain"] = [
            st.Page("src/page/200_Chat_with_Your_Data.py", icon=":material/chat:"),
            st.Page("src/page/205_Token_expiration_report.py", icon=":material/key:"),

        ]


    pg = st.navigation(pages)
    pg.run()

try:
    msg = TokenLoaderMigrate.migrate_tokens() #FutureDev: remove this after a few releases
    if msg:
        st.sidebar.success(msg)
except Exception as ex:
    st.sidebar.error(f"Error migrating tokens: {ex}")

def initialize_monitoring():
    if not APP_STATE.first_app_load: #global singleton. we only want to execute this method the first time the streamlit app loads.
        return
    APP_STATE.first_app_load = False
    if app.monitor_enable_monitoring:
        print("Initializing Monitoring")
        from src.task.health_monitor_task import HEALTH_MONITOR_TASK
        if not HEALTH_MONITOR_TASK.check_status():
            HEALTH_MONITOR_TASK.start(app.monitor_check_interval_hours)

initialize_monitoring()

