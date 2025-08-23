import json
from time import sleep
from typing import List

import streamlit as st

from src.lib.tc_api_client import TableauCloudLogin
from src.lib.tc_api_client_vizql import TCApiClientVizQl, PublishedDataSource
from src.models import AppSettings, PatToken
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.token_loader import TokenLoader


@st.dialog("Select Data Source", width="large")
def show_select_datasource_dialog(app: AppSettings, datasources: List[PublishedDataSource], tc_client, admin_pat):
    st.info("Select the Published Data Source you want to query.")
    default_index = next(
        (i for i, ds in enumerate(datasources) if ds.name == app.chat_with_tableau_selected_data_source),
        0  # Default to first item if not found
    )
    
    selected_ds = st.selectbox(
        "Data Source",
        options=datasources,
        index=default_index,
        format_func=lambda ds: ds.name,
        help="Select the published data source you want to query"
    )
    is_disabled = selected_ds.name == app.chat_with_tableau_selected_data_source
    if st.button("Save", use_container_width=True, disabled=is_disabled):
        app.chat_with_tableau_selected_data_source = selected_ds.name
        app.save()
        st.success("✓ Data source saved")
        sleep(1)
        st.rerun()
    if st.button("Read Metadata"):
        result = tc_client.get_datasource_metadata(selected_ds.luid)
        formatted_json = json.dumps(result, indent=4)
        st.code(formatted_json)
    
    with st.expander("🔍 Query Editor", expanded=False):
        default_query = """{
    "fields": [
        {
            "fieldCaption": "Car Name"
        }
    ]
}"""
        query = st.text_area("Query", value=default_query, height=200)
        
    if st.button("Query Datasource"):
        try:
            query_json = json.loads(query)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON query: {e}")
            return
        result = tc_client.query_datasource(selected_ds, query_json)
        formatted_json = json.dumps(result, indent=4)
        st.code(formatted_json)




def send_query(message: str, history: List[dict]) -> str:
    """
    Send a query to the LangChain backend and get a response
    Args:
        message: The user's message
        history: List of previous messages in the conversation
    Returns:
        str: The response from the assistant
    """
    # FutureDev: Implement actual LangChain query logic here
    return f"placeholder response"


def page_content():
    col1,col2 = st.columns([1, 1])
    col1.markdown("# :material/chat: Chat with your Data")
    with col2:
        st.markdown("")
        with st.expander("ℹ️ About this feature", expanded=False):
            st.info("""
                This feature allows you to:
                - Query your Tableau Cloud Data Sources using natural language
                - Get insights from your data through conversation
                - Explore data without writing SQL queries
                """)

    # Data Source Selection Section
    # st.markdown("#### Data Source")
    app = AppSettings.load_static()
    
    # Create two columns for data source display and selection
    col1, col2 = st.columns([3,1])
    
    # Show current data source with icon
    token_loader = TokenLoader(StreamLogger(st.container()))
    admin_token = token_loader.get_token_admin_pat()
    if app.chat_with_tableau_selected_data_source:
        col1.markdown(f"📊 Tableau Cloud Data Source: `{app.chat_with_tableau_selected_data_source}` for 🌐 site `{admin_token.sitename}`")
    else:
        col1.warning("⚠️ No data source selected")
    
    # Data source selection button
    if col2.button("Select Data Source", use_container_width=True):
        token_loader = TokenLoader(StreamLogger(st.container()))
        admin_pat = token_loader.get_token_admin_pat()
        if not admin_pat:
            st.warning("Please add an admin PAT to your settings")
        else:
            login_result = TableauCloudLogin.login(admin_pat, True)
            tc_client = TCApiClientVizQl(login_result)
            data_sources = tc_client.get_datasources_list()
            data_sources.sort(key=lambda ds: ds.name.lower())
            show_select_datasource_dialog(app, data_sources, tc_client, admin_pat)

    # Chat Section
    chat_header_col1, chat_header_col2 = st.columns([3, 1])
    chat_header_col1.markdown("#### Chat")

    if not app.chat_with_tableau_selected_data_source:
        st.warning("Please select a data source first")
        return

    # Initialize chat history in session state if it doesn't exist
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about your data"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = send_query(prompt, st.session_state.messages)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

    if st.session_state.get("messages"):
        if chat_header_col2.button("🗑️ Clear History"):
            st.session_state.messages = []
            st.rerun()


PageUtil.set_page_config("Chat with your Data", PageUtil.NO_PAGE_HEADER)
page_content()

