import subprocess
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

from src.cli.bridge_status_logic import BridgeStatusLogic
from src.lib.general_helper import TimezoneOptions
from src.lib.prompt_library import PromptLibrary, PromptPrep
from src.lib.tc_api_client import TableauCloudLogin, TCApiLogic
from src.lib.tc_api_client_jobs import TCApiClientJobs
from src.models import AppSettings
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.token_loader import TokenLoader

JOBS_DETAILS_TO_SHOW = 10

def convert_to_locale_datetime(iso_str):
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime('%c')

def install_openai_package():
    try:
        import openai
        return True
    except ImportError:
        try:
            with st.spinner(""):
                st.info("adding missing feature pip package. please wait ...")
                cmd = [sys.executable, "-m", "pip", "install", "openai"]
                with st.expander("script"):
                    st.code(' '.join(cmd), language="bash")
                subprocess.check_call(cmd)
                try:
                    import openai
                    st.success("added successfully")
                    return True
                except ImportError:
                    st.warning("Failed to install 'openai' pip package.")
                    return False
        except subprocess.CalledProcessError:
            return False

@st.dialog("Analyze with AI", width="large")
def show_summary_analysis_dialog(jobs_df, app: AppSettings):    
    with st.container(border=True):
        prompt_lib = PromptLibrary()
        prompts = prompt_lib.load_prompts()
        col1, col2 = st.columns([2,1])
        selected_prompt = col1.selectbox(
            "Which analysis would you like to perform?",
            list(prompts.keys()),
        )
        prompt = prompts[selected_prompt]        
        # STEP - Calculate statistics
        failure_count = len(jobs_df[jobs_df['Status'].str.contains('Failed', na=False)])
        bridge_agent_count = len(jobs_df['Bridge Agent'].unique()) if 'Bridge Agent' in jobs_df.columns else 0
        data_source_count = len(jobs_df['Data Source Name'].unique()) if 'Data Source Name' in jobs_df.columns else 0
        stats_cols = st.columns([1, 1, 1, 1, 1])
        stats_cols[0].caption(f"Total Jobs: {len(jobs_df):,}")
        stats_cols[1].caption(f"Failures: {failure_count:,}")
        stats_cols[2].caption(f"Bridge Agents: {bridge_agent_count:,}")
        stats_cols[3].caption(f"Data Sources: {data_source_count:,}")
        is_edit = stats_cols[4].checkbox(f":material/edit: Prompt")

        # STEP - Prepare Data
        table_string = jobs_df.to_csv(sep='\t', index=False)
        col2_container = col2.container()
    
    
    # Analysis Results Section
    if not app.openai_api_key:
        st.warning("Please add your OpenAI API key in Settings to use this feature.")
        return

    result_container = st.container(border=True)       
    col1, col2 = result_container.columns([3, 1])
    with col1:
        edited_prompt = st.text_area("Prompt", value=prompt, height=160, help="You can customize the prompt to analyze the jobs. "
                                     "Edits will override the default prompt and are stored in _bridgectl/config/user_llm_prompts.yml_. "
                                     "You can also manually edit this file.", disabled=not is_edit)
    prompt_with_log = f"{edited_prompt} \n```{table_string}```"
    estimated_tokens = PromptPrep.estimate_tokens(prompt_with_log)
    col2_container.caption(f"Model: gpt-4o-mini")
    col2_container.caption(f"Est. Tokens: {estimated_tokens:,} of max {PromptPrep.max_prompt_token_length_o1mini:,}")

    with col2:
        cont = st.container()
        prompt_with_log = f"{prompt} \n```{table_string}```"
        if is_edit:
            if st.button(":material/save: Save Prompt", use_container_width=True):
                prompt_lib.user_prompts[selected_prompt] = edited_prompt
                prompt_lib.save_user_prompts()
                st.success("Prompt saved")
                st.rerun()
            elif st.button(":material/restore: Reset to Default", use_container_width=True):
                prompt_lib.remove_user_prompt(selected_prompt)
                st.success("Prompt reset to default")
                st.rerun()
        else:
            if cont.button(":material/send: Run Analysis", use_container_width=True):
                from src.lib.gpt_logic import ChatGPTClient
                gpt = ChatGPTClient(app.openai_api_key)
                if estimated_tokens > PromptPrep.max_prompt_token_length_o1mini:
                    st.warning(f"Prompt will be truncated to max tokens.")
                
                with st.spinner("Analyzing jobs..."):
                    completion_stream = gpt.ask(prompt_with_log)
                    result_container.write_stream(completion_stream)
            else:
                result_container.info("Analyze job results with AI to gain insights.")
                if selected_prompt in prompt_lib.user_prompts:
                    st.caption("(user customized prompt)")
                

@st.dialog("Job Settings", width="large")
def show_edit_job_settings_dialog(app: AppSettings):
    # AI Analysis Settings
    api_key = None
    with st.container(border=True):
        st.markdown("### :material/memory: AI Analysis Settings")
        enable_ai_summary = st.checkbox(
            "Enable AI Analysis", 
            value=app.feature_jobs_ai_summary,
            help="Enable AI-powered job summary analysis using OpenAI's GPT model"
        )
        
        if enable_ai_summary:
            if not install_openai_package():
                st.error("Failed to install OpenAI package. Please run manually: pip install openai")
                return
                
            if app.openai_api_key:
                col1, col2 = st.columns([3,1])
                col1.success("✓ OpenAI API key is configured")
                if col2.button(":material/delete: Remove Key", type="secondary"):
                    app.openai_api_key = None
                    app.save()
                    st.success("API key removed")
                    st.stop()
            else:
                api_key = st.text_input(
                    "OpenAI API Key", 
                    value="", 
                    type="password",
                    help="API key for OpenAI services. Required for job summary analysis."
                )
   
    # Display Settings
    with st.container(border=True):
        st.markdown("### :material/schedule: Time Zone Settings")
        selected_index = 0
        if app.job_timezone_offset in TimezoneOptions.timezone_options:
            selected_index = list(TimezoneOptions.timezone_options.keys()).index(app.job_timezone_offset)
        selected_timezone = st.selectbox(
            "Job Timezone Offset", 
            TimezoneOptions.timezone_options.keys(), 
            index=selected_index,
            help="Select timezone offset from UTC for displaying job timestamps",
            format_func=lambda x: f"{x} ({TimezoneOptions.get_abbrev(x)})"
        )

    # Save Button
    st.markdown("---")
    is_changed = (
        enable_ai_summary != app.feature_jobs_ai_summary or 
        api_key or
        selected_timezone != app.job_timezone_offset
    )
    
    col1, col2 = st.columns([4,1])
    if col1.button("Save", disabled=not is_changed, use_container_width=True):
        app.feature_jobs_ai_summary = enable_ai_summary
        app.job_timezone_offset = selected_timezone
        if api_key:
            app.openai_api_key = api_key
        app.save()
        st.success("Settings saved")
        st.rerun()

    col2.page_link("src/page/81_Jobs.py", label="Close")

@st.dialog("Retry Job", width="medium")
def show_retry_job_dialog(app: AppSettings):
    st.info("Retry an extract refresh job by providing its Job ID.")
    job_id = st.text_input("Job ID", help="Enter the Job ID of the failed job you want to retry")
    
    if st.button("Start Extract Refresh", use_container_width=True):
        if not job_id:
            st.error("Please enter a Job ID")
            return
            
        with st.spinner("Starting extract refresh..."):
            try:
                s_logger = StreamLogger(st.container())
                admin_token = TokenLoader(s_logger).get_token_admin_pat()
                login_result = TableauCloudLogin.login(admin_token, True)
                api = TCApiClientJobs(login_result)
                api.start_tasks([job_id])
                st.success(f"Extract refresh started for job {job_id}")
            except Exception as e:
                st.error(f"Failed to start extract refresh: {str(e)}")

is_pool_enabled = False

def page_content():
    ch1, ch2 = st.columns([2,1])
    ch1.markdown("# :material/work: Bridge Jobs")
    st.info("This page provides an overview of recent Tableau Bridge Extract Refresh Jobs. "
            "Users can filter and sort results. "
            f"Press the include details checkbox to fetch additional details about the most recent {JOBS_DETAILS_TO_SHOW} jobs. "
            "Results are filtered by Task Type= (Bridge Refresh or Extract Refresh/Creation). "
            "Users can summarize results for deeper insights.")
    is_dialog_showing = False
    app = AppSettings.load_static()
    if ch2.button("Edit Settings"):
        show_edit_job_settings_dialog(app)
        is_dialog_showing = True
    s_logger = StreamLogger(st.container())
    c1, c2, c3, c4 = st.columns([2,1,1,1])
    token = TokenLoader(s_logger).get_token_admin_pat()
    if not token:
        return
    c1.markdown(f"Tableau Cloud [Bridge Jobs]({token.get_pod_url()}/#/site/{token.sitename}/jobs) for 🌐 site `{token.sitename}`" )
    h = f"Fetch Job Details for the {JOBS_DETAILS_TO_SHOW} most recent jobs. Also un-hides the Run Time and Queue Time columns."
    show_job_details = c2.checkbox(f"include details", help = h)
    c3.button("🔄")
    jobs_details_num = 0
    if show_job_details:
        jobs_details_num = JOBS_DETAILS_TO_SHOW

    # STEP - Fetch Jobs Report
    if is_dialog_showing:
        return
    with st.spinner("Fetching Jobs Report ..."):
        logic = BridgeStatusLogic(s_logger)
        jobs_report = logic.calculate_jobs_report(token, s_logger, jobs_details_num)
        # Fetch bridge-pool information
        if is_pool_enabled:
            login_result = TableauCloudLogin.login(token, True)
            tc_logic = TCApiLogic(login_result)
            site_id = token.site_id
            bpm_list = tc_logic.get_bridge_pool_mapping(site_id)
            pool_map = {bap.agent_name: bap.pool_name for bap in bpm_list}
    try:
        jobs = jobs_report['result']['backgroundJobs']
    except KeyError:
        jobs = None
    if not jobs:
        st.warning("No Jobs Found")
        return

    # STEP - Filter and Sort Jobs Report
    cf1, cf2, cf3, cf4 = st.columns([1,2,3,1])
    status_options = ["All", "✅ Completed", "✅ Sent to Bridge", "❗ Failed", "🕒 Pending", "🔄 In Progress"]
    status_filter = cf1.selectbox("Filter by Status", status_options)
    bridge_agents = sorted(list(set(job.get('bridge_agent', '') for job in jobs if 'bridge_agent' in job)))
    bridge_agents.insert(0, "All Agents")  # Add "All Agents" as the first option
    selected_agent = cf2.selectbox("Filter by Bridge Agent", bridge_agents)
    data_sources = sorted(list(set(job.get('data_source_name', '') for job in jobs if 'data_source_name' in job)))
    data_sources.insert(0, "All Sources")
    selected_source = cf3.selectbox("Filter by Data Source", data_sources)

    # STEP - Display Jobs Report
    cols = {
        'jobId': 'ID',
        'status': 'Status',
        'taskType': 'Task Type',
        'jobRequestedTime': 'Job Requested Time',
    }
    if any('bridge_agent' in job for job in jobs):
        cols['bridge_agent'] = 'Bridge Agent'
    if any('data_source_name' in job for job in jobs):
        cols['data_source_name'] = 'Data Source Name'
    if any('jobDescription' in job for job in jobs):
        cols['jobDescription'] = 'Description'
    if show_job_details:
        cols['jobDetails'] = 'Job Details'
        cols['currentRunTime'] = 'Run Time'
        cols['currentQueueTime'] = 'Queue Time'
    jobs_df = pd.DataFrame(jobs)
    jobs_df = jobs_df.rename(columns=cols)
    order = [v for k, v in cols.items()]
    jobs_df = jobs_df[order]
    if is_pool_enabled:
        if 'Bridge Agent' in jobs_df.columns:
            jobs_df['Pool'] = jobs_df['Bridge Agent'].map(pool_map)

    jobs_df['Status'] = jobs_df['Status'].replace('Completed', '✅ Sent to Bridge')
    jobs_df['Status'] = jobs_df['Status'].replace('BridgeExtractionCompleted', '✅ Completed')
    jobs_df['Status'] = jobs_df['Status'].replace('Failed', '❗ Failed')
    jobs_df['Status'] = jobs_df['Status'].replace('Pending', '🕒 Pending')
    jobs_df['Status'] = jobs_df['Status'].replace('InProgress', '🔄 In Progress')
    jobs_df['Task Type'] = jobs_df['Task Type'].replace('Bridge', 'Bridge Refresh')
    jobs_df['Task Type'] = jobs_df['Task Type'].replace('Extract', 'Extract Refresh/Creation')
    tz_offset_int = TimezoneOptions.get_offset_int(app.job_timezone_offset)
    tz_abbrev = TimezoneOptions.get_abbrev(app.job_timezone_offset)
    jobs_df['Job Requested Time'] = (
        pd.to_datetime(jobs_df['Job Requested Time']) 
        + pd.Timedelta(hours=tz_offset_int)
    ).dt.strftime(f'%b %d, %Y %I:%M %p {tz_abbrev}')
    total_row_count = len(jobs_df)

    # STEP -  Apply filters
    if status_filter != "All":
        jobs_df = jobs_df[jobs_df['Status'] == status_filter]
    if selected_agent != "All Agents":
        jobs_df = jobs_df[jobs_df['Bridge Agent'] == selected_agent]
    if selected_source != "All Sources":
        jobs_df = jobs_df[jobs_df['Data Source Name'] == selected_source]
    filtered_row_count = len(jobs_df)
    cf4.caption(f"Jobs: {filtered_row_count:,} / {total_row_count:,}")
    row_height = 35  # approximate height per row in pixels
    padding = 40  # extra padding for header and bottom space
    calculated_height = min(len(jobs_df) * row_height + padding, 800)
    st.dataframe(jobs_df, hide_index=True, use_container_width=True, height=calculated_height)

    if app.feature_jobs_ai_summary:
        if c4.button("Analyze with AI"):
            show_summary_analysis_dialog(jobs_df, app)

    # Add retry button after the dataframe
    # col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    # if col4.button(":material/refresh: Retry Job"):
    #     show_retry_job_dialog(app)

PageUtil.set_page_config("Bridge Jobs", PageUtil.NO_PAGE_HEADER)
page_content()
