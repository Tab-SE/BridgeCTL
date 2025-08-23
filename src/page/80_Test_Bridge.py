import dataclasses

from src.download_util import download_text
from src.models import AppSettings
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.cli.bridge_status_logic import get_or_fetch_site_id
from src.lib.tc_api_client import TableauCloudLogin, TCApiLogic
from src.lib.tc_api_client_jobs import TCApiClientJobs

import streamlit as st

from src.token_loader import TokenLoader

@dataclasses.dataclass
class TaskName:
    id: str
    target_name: str = None
    target_id: str = None


def get_tasks(sl: StreamLogger, cont):
    token = TokenLoader(sl).get_token_admin_pat()
    if not token:
        cont.warning("You can add PAT tokens on the [Settings](/Settings) page")
        return None, None

    tasks_link = f"{token.get_pod_url()}/#/site/{token.sitename}/tasks/extractRefreshes"
    cont.markdown(f"Tableau Cloud [Tasks]({tasks_link}) for 🌐 site `{token.sitename}`")
    
    with st.spinner("Fetching Extract Refresh Tasks..."):
        login_result = TableauCloudLogin.login(token, True)
        logic = TCApiLogic(login_result)
        logger = StreamLogger(st.container())
        site_id = get_or_fetch_site_id(logic.api, token, logger)

        api = TCApiClientJobs(login_result)
        tasks = api.get_tasks(site_id)
        
    task_names = []
    if tasks:
        if "errors" in tasks["result"]:
            e = tasks["result"]["errors"]
            cont.error(f"Error fetching tasks: {e}")
            return [], None
            
        for t in tasks["result"]["tasks"]:
            name = f"workbook {t['targetId']}" if t['targetType'] == "Workbook" else t['datasource_name']
            task_names.append(TaskName(id=t["id"], target_name=name, target_id=t['targetId']))
            
        for t in tasks["result"]["workbooks"]:
            tn = next((x for x in task_names if x.target_id == t["id"]), None)
            if tn:
                tn.target_name = f"Workbook {t['name']}"

        task_names.sort(key=lambda x: x.target_name.lower())
    return task_names, api


def format_task(task):
    return task.target_name


@st.dialog("Network Connectivity Test", width="large")
def show_network_test_dialog():
    st.markdown("### :material/network_check: Network Test")
    st.info("Tableau Bridge agents require access to the Tableau Online API. This test verifies network connectivity.")
    
    url = "https://online.tableau.com"
    test_container = st.container(border=True)
    
    if st.button("🔄 Run Network Test", use_container_width=True):
        with test_container:
            with st.status(f"Testing connection to {url} (port 443)..."):
                result = download_text(url)
            if result.status_code == 200:
                st.success("✅ Network connectivity test successful")
            else:
                st.error(f"❌ Network test failed (Status: {result.status_code})")
    else:
        test_container.text("Click the button above to test network connectivity")


def page_content():
    st.markdown("# :material/labs: Test Bridge Agents")
    st.info("""This page helps ensure that bridge agents are correctly configured by starting Extract Refresh Jobs.
             After starting a task, you can monitor the status on the [Jobs](/Jobs) page.""")

    col1, col2 = st.columns([1,1])
    # SECTION - Extract Refreshs
    with col1.container(border=True):
        st.markdown("### :material/refresh: Start Extract Refresh")
        sl = StreamLogger(st.container())
        names, api = get_tasks(sl, st)
        if not names:
            st.warning("No extract refresh tasks found")
            return
        names.insert(0, TaskName(id=None, target_name=""))
        form = st.form(key="start_task")
        selected = form.selectbox(
            "Select Extract Refresh Task", 
            names,
            format_func=format_task,
            help="Choose a task to refresh"
        )
        if form.form_submit_button("▶️ Start Task", use_container_width=True):
            if not selected.id:
                st.warning("Please select a task")
            else:
                api.start_tasks([selected.id])
                st.success(f"✅ Job started for {selected.target_name}")
    
    # SECTION - Network Test
    if col2.button(":material/network_check: Network Test", use_container_width=True):
        show_network_test_dialog()


PageUtil.set_page_config("Test Bridge", PageUtil.NO_PAGE_HEADER)
page_content()

