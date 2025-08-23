import json
from time import sleep
from typing import List
from datetime import datetime, timezone
import pandas as pd

import streamlit as st

from src.lib.tc_api_client import TableauCloudLogin, TCApiClient
from src.lib.tc_api_client_vizql import TCApiClientVizQl, PublishedDataSource
from src.models import AppSettings, PatToken
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.token_loader import TokenLoader


def format_date(date_str):
    """Format date string to a more readable format"""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("+00:00", "Z"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return date_str


def parse_date(date_str):
    """Parse date string to datetime object with proper timezone handling"""
    if not date_str:
        return None
    try:
        # Replace +00:00 with Z for ISO format compatibility
        date_str = date_str.replace("+00:00", "+0000")
        # Parse the date with timezone awareness
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    except Exception:
        try:
            # Try alternative format without microseconds
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        except Exception:
            return None


def calculate_days_until_expiration(expiry_date):
    """Calculate days until expiration with proper timezone handling"""
    if not expiry_date:
        return "Unknown"
    
    # Get current time with timezone awareness
    now = datetime.now(timezone.utc)
    
    # Calculate the difference
    delta = expiry_date - now
    return delta.days


def get_token_expiration_info():
    """Get token expiration information from Tableau Cloud"""
    token_loader = TokenLoader(StreamLogger(st.container()))
    admin_token = token_loader.get_token_admin_pat()
    
    if not admin_token:
        st.warning("⚠️ No admin PAT token found. Please add an admin PAT token in Settings.")
        return None, None, None
    
    with st.spinner("Connecting to Tableau Cloud..."):
        login_result = TableauCloudLogin.login(admin_token)
        
        if not login_result.is_success:
            st.error(f"❌ Failed to connect to Tableau Cloud: {login_result.error}")
            return None, None, None
        
        try:
            api_client = TCApiClient(login_result)
            session_info = api_client.get_session_info()
            user_id = session_info["result"]["user"]["systemUserId"]
            user_email = session_info["result"]["user"]["username"]
            site_name = admin_token.sitename
            
            token_info = api_client.get_personal_access_token_info(user_id)
            api_client.logout()            
            return token_info, user_email, site_name
        except Exception as e:
            st.error(f"❌ Error retrieving token information: {str(e)}")
            return None, None, None


def page_content():
    st.markdown("# :material/key: Token Expiration Report")
        
    # Get token information including user email and site name
    token_info, user_email, site_name = get_token_expiration_info()
    
    # Display user and site information
    col1, col2 = st.columns([2, 3])
    if user_email and site_name:
        col1.markdown(f"🌐 Site: `{site_name}` • 👤 User: `{user_email}`")
    with col2:
        with st.expander("ℹ️ Instructions", expanded=False):
            st.info("""
                This report shows all Personal Access Tokens (PATs) for your Tableau Cloud user account, 
                including when they were last used and when they will expire.                
            """)

    if not token_info or "result" not in token_info or "tokenInfos" not in token_info["result"]:
        st.warning("No token information found.")
        return
        
    tokens = token_info["result"]["tokenInfos"]
    if not tokens:
        st.warning("No tokens found for this user.")
        return
    
    # Create DataFrame for display
    data = []
    for token in tokens:
        expiry_date = parse_date(token.get("expiresAt", ""))
        data.append({
            "Token Name": token.get("clientId", "Unknown"),
            "Last Used": format_date(token.get("lastUsedAt", "")),
            "Expires": format_date(token.get("expiresAt", "")),
            "Days Until Expiration": calculate_days_until_expiration(expiry_date)
        })
    
    df = pd.DataFrame(data)
    
    # Sort by expiration date (ascending)
    df = df.sort_values(by="Days Until Expiration")
    
    # Add color highlighting based on expiration
    def highlight_expiration(val):
        if isinstance(val, int):
            if val < 30:
                return 'background-color: #FFCCCC'  # Red for < 30 days
            elif val < 90:
                return 'background-color: #FFFFCC'  # Yellow for < 90 days
            else:
                return 'background-color: #CCFFCC'  # Green for >= 90 days
        return ''
    
    # Display the table with styling
    st.markdown("### Token Expiration Summary")
    styled_df = df.style.applymap(highlight_expiration, subset=["Days Until Expiration"])
    st.dataframe(styled_df, use_container_width=True)
    
    # Summary statistics
    st.markdown("### Summary")
    col1, col2, col3 = st.columns(3)
    
    expiring_soon = sum(1 for days in df["Days Until Expiration"] if isinstance(days, int) and days < 30)
    col1.metric("Tokens Expiring Soon (<30 days)", expiring_soon)
    col2.metric("Total Tokens", len(tokens))
    
    # Find oldest last used with proper error handling
    try:
        last_used_dates = [parse_date(token.get("lastUsedAt", "")) 
                          for token in tokens if token.get("lastUsedAt")]
        last_used_dates = [d for d in last_used_dates if d is not None]
        
        if last_used_dates:
            oldest_used = min(last_used_dates)
            col3.metric("Oldest Last Used", oldest_used.strftime("%Y-%m-%d"))
    except Exception as e:
        st.error(f"Error calculating oldest last used: {str(e)}")


PageUtil.set_page_config("Token Expiration Report", PageUtil.NO_PAGE_HEADER)
page_content()

