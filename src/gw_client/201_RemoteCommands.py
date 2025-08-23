from time import sleep

import streamlit as st

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.gw_client.dc_gw_client import DcGwClient
from src.gw_client.dc_gw_config import REMOTE_COMMAND_INTERVAL_SECONDS
from src.lib.general_helper import StringUtils, MachineHelper
from src.gw_client.remote_commands_task import REMOTE_COMMANDS
from src.token_loader import TokenLoader


def is_valid(check_int):
    if not check_int:
        return False
    try:
        check_int = float(check_int)
    except ValueError:
        st.warning("check statis interval must be a number")
        return False
    if check_int < 0.1:
        st.warning("check status interval must be >= 0.1")
        return False
    if check_int > 24:
        st.warning("check status interval must <= 24")
        return False
    return True


# @st.dialog("Edit Monitoring Settings", width="large")
# def edit_monitoring_settings(app: AppSettings):
#     slack_email = st.text_input("slack notification email:", app.monitor_slack_recipient_email)
#     st.html("""<style>[title="Show password text"] {display: none;}</style>""")
#     slack_api_key = st.text_input("Slack api key", app.monitor_slack_api_key, type="password", help="Enter the slack api key for your slack app.")
#     pager_duty_key = st.text_input("Pager duty routing key:", app.monitor_pager_duty_routing_key, type="password")
#     check_interval_hours = st.text_input("Check status every (hours):", app.monitor_check_interval_hours)
#     p = ','.join(app.monitor_only_pools) if app.monitor_only_pools else ""
#     selected_monitor_pools = st.text_input("Only Monitor these Pools (comma separated):", p)
#     selected_monitor_pools = [s.strip() for s in selected_monitor_pools.split(",")] if selected_monitor_pools else []
#
#     is_disabled = True
#     if is_valid(slack_email, slack_api_key, pager_duty_key, check_interval_hours):
#         if (slack_api_key != app.monitor_slack_api_key
#                 or slack_email != app.monitor_slack_recipient_email
#                 or pager_duty_key != app.monitor_pager_duty_routing_key
#                 or check_interval_hours != app.monitor_check_interval_hours
#                 or selected_monitor_pools != app.monitor_only_pools):
#             is_disabled = False
#     if st.button("Save", disabled=is_disabled):
#         app.monitor_slack_api_key = slack_api_key
#         app.monitor_slack_recipient_email = slack_email
#         app.monitor_pager_duty_routing_key = pager_duty_key
#         app.monitor_check_interval_hours = float(check_interval_hours)
#         app.monitor_only_pools = selected_monitor_pools
#         app.save()
#         BRIDGE_HEALTH_MONITOR.change_settings(app)
#         BRIDGE_HEALTH_MONITOR.run_now()
#         st.success("saved")
#         st.toast("saved, press refresh to see latest status.")
#         sleep(1)
#         st.rerun()


def page_content():
    st.info(f"""A background job will check regularly remote commands to be executed from API Gateway""")
    token_loader = TokenLoader(StreamLogger(st.container()))
    admin_pat = token_loader.get_token_admin_pat()
    if not admin_pat:
        st.warning("unable to login to gw api without a valid 'admin-pat' tableau cloud token")
        return
    col1, col2 = st.columns(2)
    bst = token_loader.load()
    if not bst.site.gw_api_token:
        if col1.button("Login", disabled=not admin_pat):
            client = DcGwClient()
            payload = {"pat_name": admin_pat.name, "secret": admin_pat.secret, "site_name": admin_pat.sitename,
                       "pod_url": admin_pat.pod_url, "site_luid": admin_pat.site_luid,
                       "machine_name": MachineHelper.get_hostname()}
            ret = client.edge_manager_register(admin_pat.site_luid, payload)
            new_id = ret["edge_manager_id"]
            if not new_id:
                raise Exception("new edge_manager_id not found in response")
            token_loader.update_edge_manager_id(new_id, ret["gw_token"])
            st.rerun()
        else:
            return
    else:
        if col2.button("Logout"):
            token_loader.update_edge_manager_id(None, None)
            st.rerun()
    col1.success("Logged in to gateway api")

    is_alive = REMOTE_COMMANDS.check_status()
    status = "running" if is_alive else "stopped"

    col1.markdown(f"Remote Commands Status: `{status}`")
    # if col2.button("Edit"):
    #     edit_monitoring_settings(app)
    col1.markdown(f"Check status every: `{REMOTE_COMMAND_INTERVAL_SECONDS}` seconds")
    # p = ','.join(app.monitor_only_pools) if app.monitor_only_pools else "(all)"
    # col1.markdown(f"Monitor selected pools: `{p}`")
    # col1.markdown("---")

    if not is_alive:
        if st.button("Start Remote Commands monitoring"):
            with st.spinner("starting ..."):
                REMOTE_COMMANDS.change_settings(bst.site)
                REMOTE_COMMANDS.start()
                st.success("Remote Commands monitoring Started")
                sleep(5)
                st.rerun()
    else:
        if st.button("Stop Remote Commands monitoring"):
            with st.spinner("stopping ..."):
                REMOTE_COMMANDS.stop()
                REMOTE_COMMANDS.last_message = ""
                REMOTE_COMMANDS.last_run = None
                st.warning("Remote Commands monitoring Stopped")
                sleep(2)
                st.rerun()

    short_time_ago = f", `{StringUtils.short_time_ago(REMOTE_COMMANDS.last_run)}` ago" if REMOTE_COMMANDS.last_run else ""
    st.markdown(f"Last time run: `{REMOTE_COMMANDS.last_run}` {short_time_ago}")

    if REMOTE_COMMANDS.last_message:
        st.markdown("Last message:")
        cont = st.container(border=True)
        cont.text(f"{REMOTE_COMMANDS.last_message}")
    if st.button("🔄"):
        st.rerun()


PageUtil.set_page_config("Remote Commands monitoring", "Remote Commands monitoring", True)
page_content()
