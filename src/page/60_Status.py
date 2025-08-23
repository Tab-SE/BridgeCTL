import pandas as pd
import streamlit as st

from src.page.ui_lib.pat_tokens_ui import show_change_site_dialog
from src.page.ui_lib.stream_logger import StreamLogger

from src.page.ui_lib.page_util import PageUtil
from src.cli import bridge_status_logic
from src.token_loader import TokenLoader
from src.lib.general_helper import TimezoneOptions
from src.models import AppSettings


def page_content():
    s_logger = StreamLogger(st.container())
    token_loader = TokenLoader(s_logger)
    st.info("View the assigned pool and connectivity status of your Bridge agents.")
    
    # Get admin token and validate
    admin_token = token_loader.get_token_admin_pat()
    if not admin_token:
        return
    app = AppSettings.load_static()
    
    # Header section with site info and controls
    with st.container(border=True):
        col1, col2 = st.columns([2,1])
        
        # Site information
        with col1:
            st.markdown(f"### 🌐 Site: `{admin_token.sitename}`")
            st.markdown(f"Tableau Cloud [Bridge Settings]({admin_token.get_bridge_settings_url()})")
        
        # Controls
        with col2:
            col2a, col2b = st.columns([1,1])
            if token_loader.have_additional_token_yml_site_files():
                if col2a.button(":material/swap_horiz: Change Site", use_container_width=True):
                    show_change_site_dialog(token_loader)
            if col2b.button("🔄"):
                st.rerun()
    
    # Agent Status Table
    with st.container(border=True):
        st.markdown("### 📊 Bridge Agent Status")
        with st.spinner("Fetching status..."):
            agents_status, headers = bridge_status_logic.display_bridge_status(admin_token, s_logger, True)
        
        if not agents_status:
            st.info("No Bridge agents found for this site")
            return
            
        # Create and format DataFrame
        df = pd.DataFrame(agents_status, columns=headers)
        
        # Format status column with emojis
        s_col = 'Connection Status'
        df[s_col] = df[s_col].replace({
            'CONNECTED': '✅ Connected',
            'DISCONNECTED': '❌ Disconnected',
            'NOT_RESPONSIVE': '❌ Not Responding'
        })
        
        # Format timestamp with timezone
        if 'Last Connected' in df.columns:
            tz_offset_int = TimezoneOptions.get_offset_int(app.job_timezone_offset)
            tz_abbrev = TimezoneOptions.get_abbrev(app.job_timezone_offset)
            df['Last Connected'] = (
                pd.to_datetime(df['Last Connected']) 
                + pd.Timedelta(hours=tz_offset_int)
            ).dt.strftime(f'%b %d, %Y %I:%M %p {tz_abbrev}')
        
        # Calculate dynamic height based on number of rows
        height = min(len(df) * 35 + 40, 800)  # Cap at 800px
        
        # Display metrics
        metric_cols = st.columns(4)
        total_agents = len(df)
        connected = len(df[df[s_col] == '✅ Connected'])
        unhealthy = len(df[df[s_col] != '✅ Connected'])
        
        metric_cols[0].metric("Total Agents", total_agents)
        metric_cols[1].metric("Connected", connected, help="Number of agents currently connected")
        metric_cols[2].metric("Disconnected", unhealthy, help="Number of agents currently not connected")
        
        # Display the dataframe
        st.dataframe(df, hide_index=True, height=height)


PageUtil.set_page_config("Bridge Agent Status", ":material/monitor_heart: Bridge Agent Status")
page_content()
