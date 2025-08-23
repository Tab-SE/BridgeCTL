from time import sleep

import streamlit as st

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.docker_client import DockerClient
from src.gw_client.dc_gw_client import DcGwClient
from src.gw_client.dc_gw_client_models import UpdateCommandDto, ActionState, ActionResults, Cols, \
    EdgeManagerDto, \
    GwActions, ParamNames
from src.gw_client.remote_commands_logic import RemoteCommandLogic
from src.lib.general_helper import MachineHelper, StringUtils
from src.models import TokenSite
from src.os_type import current_os
from src.token_loader import TokenLoader


def update_edge_state(ts: TokenSite, col2):
    if col2.button("Update edge network state"):
        with st.spinner(""):
            client2 = DcGwClient(ts.gw_api_token)

            docker_client = DockerClient(StreamLogger(st.container()))
            bridge_container_names = docker_client.get_bridge_container_names()
            details = []
            for name in bridge_container_names:
                detail = docker_client.get_container_details(name, False)
                d = detail.get_serializable()
                d[ParamNames.bridge_container_name] = name
                details.append(d)
            os = str(current_os())
            payload = {Cols.edge_manager_id: ts.edge_manager_id, Cols.machine_name: MachineHelper.get_hostname(), Cols.os_type: os, Cols.site_name:ts.sitename, Cols.detail: details}
            client2.edge_manager_update(payload)


def get_edge_network(ts: TokenSite, gw: DcGwClient, cola):
    client2 = DcGwClient(ts.gw_api_token)
    ret = client2.edge_manager_all_by_site()
    if not ret:
        cola.warning("no edge network found")
        return
    edge_managers = []
    for em in ret:
        emd = EdgeManagerDto(em[Cols.edge_manager_id], em[Cols.machine_name], em[Cols.site_name], em[Cols.os_type], em[Cols.detail])
        edge_managers.append(emd)

    for idx, emd in enumerate(edge_managers):
        col1, col2 = cola.columns([2, 1])
        col1.markdown(f"#### :material/dns: Edge Manager {emd.display_name()}")
        if emd.detail:
            for bridge_agent in emd.detail:
                agent_name = bridge_agent['labels']['tableau_bridge_agent_name']
                col1.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;:material/cloud_sync: {agent_name}")
        else:
            col1.markdown("&nbsp;&nbsp;&nbsp;&nbsp;no bridge agents found")
        if col2.button(f":material/info: Action", key=f"actions_{idx}"):
            dialog_send_remote_command(ts, gw, emd)


@st.dialog("Get Remote Command", width="large")
def render_get_remote_commands(gw: DcGwClient):
    st.columns(2)[1].markdown("Edge Gateway URL: " + gw.base_url)
    include_all = st.checkbox("include completed")
    my_commands = gw.get_commands(not include_all)
    if not my_commands:
        st.warning("no new commands found")
        selected_command = None
    else:
        selected_command = st.selectbox("Select Command to run", my_commands, format_func=lambda x: f"{x.id} - {x.action}")
    if st.button("run action", disabled=not bool(selected_command)):
        with st.spinner("running command"):
            logic = RemoteCommandLogic(StreamLogger(st.container()))
            result, detail = logic.route_command(selected_command)
            if result == ActionResults.success:
                st.success(detail)
            else:
                st.error(detail)
    else:
        st.json(my_commands)

@st.dialog("Send Remote Command", width="large")
def dialog_send_remote_command(ts: TokenSite, gw: DcGwClient, selected_target: EdgeManagerDto):
    st.markdown(f"Send Command to &nbsp;&nbsp;&nbsp; :material/dns: `{selected_target.display_name()}`")
    actions = StringUtils.get_values_from_class(GwActions)
    selected_action = st.selectbox("Action", actions)
    parameters = {}
    if selected_action == GwActions.remove_bridge_agent:
        names = []
        for bridge_agent in selected_target.detail:
            bridge_container_name = bridge_agent[ParamNames.bridge_container_name]
            names.append(bridge_container_name)
        name = st.selectbox("Bridge Agent container to remove", names)
        parameters[ParamNames.bridge_container_name] = name
    payload = {
        "target_edge_manager_id": selected_target.id,
        "source_edge_manager_id": ts.edge_manager_id,
        "action": selected_action,
        "parameters": parameters
    }
    if st.button("Send Command"):
        ret = gw.send_new_command(payload)
        st.subheader("response: ")
        st.code(ret, language="json")

def page_content():
    st.info("Show all bridge agents connected to the site `fluke23` as reported by bridgectl clients whether the agents "
            "are hosted in Docker or Kubernetes. "
            "In the future you will be able to see useful details about each bridge agent, including: "
            " bridge rpm version, drivers installed, connected pool, etc. \n"
            "You will also be able to remotely manage the agents: upgrade the bridge rpm, install new driers, scale up additional agents, stop an agent, etc.")

    admin_pat = TokenLoader(StreamLogger(st.container())).get_token_admin_pat()
    if not admin_pat:
        st.warning("unable to login to gw api without a valid 'admin-pat' tableau cloud token")
        return
    # app = AppSettings.load_static()
    token_loader = TokenLoader(StreamLogger(st.container()))
    bst = token_loader.load()
    cola, colb = st.columns([2,1])
    cx, cy = colb.columns([3,1])
    cx.markdown(f"Network Map of bridge agents for site `{admin_pat.sitename}`")
    if cy.button("🔄"):
        st.rerun()

    if not bst.site.gw_api_token:
        if cola.button("Login", disabled=not admin_pat):
            client = DcGwClient(None)
            payload = {"pat_name": admin_pat.name, "secret": admin_pat.secret, "site_name": admin_pat.sitename,
                       "pod_url": admin_pat.pod_url, "site_luid": admin_pat.site_luid,
                       "machine_name": MachineHelper.get_hostname()}
            with st.spinner(""):
                ret = client.edge_manager_register(payload)
            new_id = ret["edge_manager_id"]
            if not new_id:
                raise Exception("new edge_manager_id not found in response")
            bst.site.edge_manager_id = new_id
            bst.site.gw_api_token = ret["gw_token"]
            token_loader.update_edge_manager_id(bst.site.edge_manager_id, bst.site.gw_api_token)
            st.rerun()
        else:
            return
    else:
        em = EdgeManagerDto(bst.site.edge_manager_id, MachineHelper.get_hostname(), bst.site.sitename, str(current_os()), None)
        colb.success(f"Logged in to gateway api &nbsp;&nbsp;&nbsp; :material/dns: `{em.display_name()}`")
        if colb.button("Logout"):
            with st.spinner(""):
                DcGwClient(bst.site.gw_api_token).edge_manager_unregister()
            colb.success("unregistered edge_manager")
            token_loader.update_edge_manager_id("", "")
            sleep(1)
            st.rerun()

    exp = colb.expander("...")
    update_edge_state(bst.site, exp)

    gw = DcGwClient(bst.site.gw_api_token)
    get_edge_network(bst.site, gw, cola)

    if exp.button("get remote commands"):
        render_get_remote_commands(gw)



PageUtil.set_page_config(page_title="Edge Network", page_header="Edge Network")
page_content()
