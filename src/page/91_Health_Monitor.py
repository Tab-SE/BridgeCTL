import re
from time import sleep

import streamlit as st

from src.cli.app_config import APP_CONFIG, APP_NAME
from src.cli.bridge_status_logic import get_or_fetch_site_id
from src.lib.general_helper import StringUtils
from src.lib.tc_api_client import TableauCloudLogin, TCApiLogic
from src.models import AppSettings
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.task.health_monitor_task import HEALTH_MONITOR_TASK, AgentHealthCategory
from src.token_loader import TokenLoader
from src.validation_helper import ValidationHelper


def is_valid(email, slack_channel_id, slack_api_key, pager_duty_key):
    if email and not ValidationHelper.is_valid_email(email):
        st.warning("Invalid email")
        return False
    if slack_channel_id:
        pattern = r'^[CDG][A-Z0-9]{8,}$'
        if not re.match(pattern, slack_channel_id):
            st.warning(f"Invalid Slack channel ID. It should be in the format `{pattern}`")
            return False
    return True

def is_check_interval_hours_valid2(check_interval_hours: str):
    if not check_interval_hours:
        return None
    try:
        check_interval_hours = float(check_interval_hours)
    except ValueError:
        st.warning("Invalid check interval. Please enter a valid number between 0.1 and 24")
        return None
    if check_interval_hours < 0.1:
        st.warning("Check interval should be at least 0.1 hours")
        return None
    if check_interval_hours > 24:
        st.warning("Check interval should not exceed 24 hours")
        return None
    return check_interval_hours

def auto_heal(): #FutureDev
    app =AppSettings.load_static()
    min_agents = app.monitor_auto_heal_min_agents
    auto_heal_enable = app.monitor_auto_heal_enable
    if APP_CONFIG.is_internal_build() and False:
        selected_pools = []
        auto_heal_enable = st.checkbox("Enable Auto Healing", value=app.monitor_auto_heal_enable, disabled=len(selected_pools) != 1)
        if len(selected_pools) != 1:
            st.warning("Auto Scaling can only be enabled for a single pool")
        else:
            if auto_heal_enable:
                min_agents = st.number_input("Auto Healing Minimum Connected Agents", value=app.monitor_auto_heal_min_agents)

@st.dialog("Edit Monitoring Settings", width="large")
def edit_monitoring_settings(app: AppSettings):
    # SECTION -Slack
    st.subheader("Slack")
    col1, col2 = st.columns(2)
    slack_email = col1.text_input("Slack notification email:", app.monitor_slack_recipient_email)
    slack_channel_id = col2.text_input("Slack notification Channel ID:", app.monitor_slack_recipient_channel_id, help="Enter the slack channel ID to send notifications to. This can be found at the very bottom of the channel details dialog.")
    
    slack_api_key = None
    if app.monitor_slack_api_key:
        col1, col2 = st.columns([1,1])
        col1.markdown("Slack API key: *****")
        if col2.button("Remove slack api key"):
            app.monitor_slack_api_key = None
            app.save()
            col2.success("Slack API key removed")
            st.stop()
    else:
        slack_api_key = st.text_input("Slack api key", "", type="password", help="Enter the slack api key for your slack app.")
    # SECTION - Pager Duty
    st.subheader("Pager Duty")
    pager_duty_key = None
    if app.monitor_pager_duty_routing_key:
        col1, col2 = st.columns([1,1])
        col1.markdown("Pager Duty routing key: *****")
        if col2.button("Remove Pager Duty key"):
            app.monitor_pager_duty_routing_key = None
            app.save()
            col2.success("Pager Duty key removed")
            sleep(1)
            st.rerun()
    else:
        pager_duty_key = st.text_input("Pager duty routing key:", "", type="password")

    # SECTION - New Relic
    st.subheader("New Relic")
    newrelic_insert_key = None
    newrelic_account_id = None
    if app.monitor_newrelic_insert_key or app.monitor_newrelic_account_id:
        col1, col2 = st.columns([1,1])
        col1.markdown("New Relic credentials: *****")
        if col2.button("Remove New Relic credentials"):
            app.monitor_newrelic_insert_key = None
            app.monitor_newrelic_account_id = None
            app.save()
            col2.success("New Relic credentials removed")
            st.stop()
    else:
        col1, col2 = st.columns(2)
        newrelic_insert_key = col1.text_input("New Relic Insert Key:", "", type="password")
        newrelic_account_id = col2.text_input("New Relic Account ID:", "", help="Your New Relic account ID")
    st.subheader("Check Interval")
    check_interval_hours = st.text_input("Check status every (hours):", app.monitor_check_interval_hours)
    check_interval_float = is_check_interval_hours_valid2(check_interval_hours)
    if not check_interval_float:
        return

    # STEP - Save settings
    is_disabled = True
    if is_valid(slack_email, slack_channel_id, slack_api_key, pager_duty_key):
        if (slack_api_key
                or slack_email != app.monitor_slack_recipient_email
                or slack_channel_id != app.monitor_slack_recipient_channel_id
                or pager_duty_key
                or newrelic_insert_key
                or check_interval_float != app.monitor_check_interval_hours
                ):
            is_disabled = False
    if st.button("Save", disabled=is_disabled):
        if slack_api_key:
            app.monitor_slack_api_key = slack_api_key
        app.monitor_slack_recipient_email = slack_email
        app.monitor_slack_recipient_channel_id = slack_channel_id
        if pager_duty_key:  
            app.monitor_pager_duty_routing_key = pager_duty_key
        if newrelic_insert_key:
            app.monitor_newrelic_insert_key = newrelic_insert_key
            app.monitor_newrelic_account_id = newrelic_account_id
        app.monitor_check_interval_hours = check_interval_float
        app.save()
        if check_interval_hours != app.monitor_check_interval_hours:
            HEALTH_MONITOR_TASK.change_interval(app.monitor_check_interval_hours)
        HEALTH_MONITOR_TASK.trigger_run_now()
        st.success("saved")
        st.toast("saved, press refresh to see latest status.")
        st.rerun()

@st.dialog("Test Notifications", width="medium")
def show_test_notification_dialog(app):
    test_message = f"Test notification from {APP_NAME}"
    st.info(f"Send a test notification. If everything is configured correctly you will receive the message \n\n`{test_message}`")
    selected_slack = st.checkbox("Send to Slack", value=app.monitor_slack_api_key is not None, disabled=app.monitor_slack_api_key is None)
    selected_pager_duty = st.checkbox("Send to Pager Duty", value= app.monitor_pager_duty_routing_key is not None, disabled= app.monitor_pager_duty_routing_key is None)
    selected_newrelic = st.checkbox("Send to New Relic", value= app.monitor_newrelic_insert_key is not None and app.monitor_newrelic_account_id is not None, disabled= app.monitor_newrelic_insert_key is None or app.monitor_newrelic_account_id is None)
    if st.button("Send", disabled=not selected_slack and not selected_pager_duty and not selected_newrelic):
        sl = StreamLogger(st.container())
        is_success, msg = HEALTH_MONITOR_TASK.send_test_notification(app, selected_slack, selected_pager_duty, selected_newrelic, test_message, sl)

def get_pool_list_helper():
    with st.spinner(""):
        token_loader = TokenLoader(StreamLogger(st.container()))
        admin_pat = token_loader.get_token_admin_pat()
        login_result = TableauCloudLogin.login(admin_pat, True)
        logic = TCApiLogic(login_result)
        site_id = get_or_fetch_site_id(logic.api, admin_pat, StreamLogger(st.container()))
        pool_list = logic.get_pool_list(site_id)
        return [x.name for x in pool_list]


@st.dialog("Edit Monitored Pools", width="small")
def edit_monitored_pools(app: AppSettings, pool_list: list):
    # Filter out any invalid pools from the default value and warn about them
    valid_defaults = [pool for pool in (app.monitor_only_pools or []) if pool in pool_list]
    if app.monitor_only_pools:
        invalid_pools = [pool for pool in app.monitor_only_pools if pool not in pool_list]
        if invalid_pools:
            st.warning(f"Some previously selected pools are no longer available: {','.join(invalid_pools)}")
    
    st.info("Select the pools to monitor. Leave blank to monitor all bridge agents in all pools.")

    # Pool selection using filtered valid defaults
    # with st.form("pool_selection_form"):
    selected_pools = st.multiselect(
        "Bridge Pool to monitor",
        options=pool_list,
        default=valid_defaults if valid_defaults else None,  # Use None if no valid defaults
        placeholder="Select a pool",
    )
    if st.button("Save"):
        app.monitor_only_pools = selected_pools if selected_pools else None
        app.save()
        HEALTH_MONITOR_TASK.trigger_run_now()
        st.success("Saved pool selection")
        st.toast("Pool selection updated, press refresh to see latest status.")
        st.rerun()

def page_content():
    st.info("""A background job will check regularly if any of the bridge agents are not connected by calling the Tableau Cloud APIs.
             Notifications will be sent via Slack, PagerDuty, and/or New Relic.""")
    
    app = AppSettings.load_static()
    is_alive = HEALTH_MONITOR_TASK.check_status()
    status = "🟢 Running" if is_alive else "⚪ Stopped"
    col1, col2, col3 = st.columns([2,1,1])
    col1.markdown(f"### Monitoring Status: {status}")
    if col2.button("⚙️ Settings", use_container_width=True):
        edit_monitoring_settings(app)
    if col3.button("🔔 Test Alerts", use_container_width=True):
        show_test_notification_dialog(app)

    with st.container():
        config_col1, config_col2 = st.columns(2)
        
        with config_col1:
            st.markdown(f"🕒 Check Interval: `{app.monitor_check_interval_hours}` hours")
            # Modified pool display with edit button
            pools_col1, pools_col2 = st.columns([3, 1])
            pools = ','.join(app.monitor_only_pools) if app.monitor_only_pools else "All Pools"
            pools_col1.markdown(f"🔍 Monitored Pools: `{pools}`")
            if pools_col2.button("Edit", key="edit_pools"):
                pool_names = get_pool_list_helper()
                edit_monitored_pools(app, pool_names)
            
            token = TokenLoader(StreamLogger(st.container())).get_token_admin_pat()
            if token:
                st.markdown(f"🌐 Site: `{token.sitename}`")
            
            if app.monitor_auto_heal_enable:
                st.markdown("**Auto Healing**")
                st.markdown(f"✅ Enabled with `{app.monitor_auto_heal_min_agents}` minimum agents")

        with config_col2:
            st.markdown("**Alert Channels**")
            
            # Slack status
            slack_status = "✅ Enabled" if app.monitor_slack_api_key else "Disabled"
            slack_details = []
            if app.monitor_slack_recipient_email:
                slack_details.append(f"Email: `{app.monitor_slack_recipient_email}`")
            if app.monitor_slack_recipient_channel_id:
                slack_details.append(f"Channel: `{app.monitor_slack_recipient_channel_id}`")
            slack_info = f" ({', '.join(slack_details)})" if slack_details else ""
            st.markdown(f":material/notification_important: Slack: {slack_status}{slack_info}")
            
            # PagerDuty status
            pagerduty_status = "✅ Enabled" if app.monitor_pager_duty_routing_key else "Disabled"
            st.markdown(f":material/notification_important: PagerDuty: {pagerduty_status}")
            
            # New Relic status
            newrelic_status = "✅ Enabled" if (app.monitor_newrelic_insert_key and app.monitor_newrelic_account_id) else "Disabled"
            newrelic_info = f" (Account: `{app.monitor_newrelic_account_id}`)" if app.monitor_newrelic_account_id else ""
            st.markdown(f":material/notification_important: New Relic: {newrelic_status}{newrelic_info}")

    # Control buttons
    st.markdown("---")
    if not is_alive:
        if st.button("▶️ Start Monitoring", use_container_width=True):
            with st.spinner("Starting monitoring service..."):
                app.monitor_enable_monitoring = True
                app.save()
                HEALTH_MONITOR_TASK.start(app.monitor_check_interval_hours)
                st.success("✅ Monitoring Started")
                sleep(2)
                st.rerun()
    else:
        if st.button("⏹️ Stop Monitoring", use_container_width=True, type="secondary"):
            with st.spinner("Stopping monitoring service..."):
                app.monitor_enable_monitoring = False
                app.save()
                HEALTH_MONITOR_TASK.stop()
                HEALTH_MONITOR_TASK.last_message = ""
                HEALTH_MONITOR_TASK.last_run = None
                st.warning("⚫ Monitoring Stopped")
                sleep(2)
                st.rerun()

    # Last run information
    if HEALTH_MONITOR_TASK.last_run:
        st.markdown("#### Last Run Status")
        status_cols = st.columns([2,1])
        with status_cols[0]:
            st.markdown(f"🕒 Last Check: `{StringUtils.short_time_ago(HEALTH_MONITOR_TASK.last_run)}` ago")
        with status_cols[1]:
            if st.button("🔄", help="Refresh status information"):
                st.rerun()

    # Last message with proper formatting
    if HEALTH_MONITOR_TASK.last_message:
        st.markdown("#### Last Alert Message")
        message_container = st.container(border=True)
        message_container.text(HEALTH_MONITOR_TASK.last_message)
        
        if HEALTH_MONITOR_TASK.last_message_health == AgentHealthCategory.healthy:
            message_container.success("✅ All monitored agents are healthy")
        else:
            message_container.warning("⚠️ Some monitored agents are unhealthy")

    if app.monitor_enable_monitoring:
        if st.button("trigger healthcheck now", help="triggers the monitoring task to run now and check that all agents are connected"):
            with st.spinner(""):
                HEALTH_MONITOR_TASK.trigger_run_now()
                sleep(2)
                st.rerun()


PageUtil.set_page_config("Monitor Bridge Agent Health", ":material/monitoring: Monitor Bridge Agent Health")
page_content()

