import os
import re
from time import sleep

import streamlit as st
import yaml

from src.cli.app_config import APP_CONFIG
from src.page.ui_lib.stream_logger import StreamLogger
from src.enums import ADMIN_PAT_PREFIX
from src.lib.general_helper import StringUtils
from src.lib.tc_api_client import TCApiLogic, TableauCloudLogin
from src.models import PatToken, BridgeSiteTokens, PatTokenSecret
from src.token_loader import TokenLoader, token_file_path


def validate_token(t_name, t_secret, t_site_name, t_pod_url, t_comment, new_site):
    # Required field checks
    if not t_name:
        st.warning("token name is required")
        return None
    if not t_secret:
        st.warning("token secret is required")
        return None
    if not t_site_name:
        st.warning("Sitename is required")
        return None
        
    # Validate token name pattern
    if not t_name.startswith(ADMIN_PAT_PREFIX):
        pattern = r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"
        if not re.match(pattern, t_name):
            st.warning(f"PAT Token name `{t_name}` is not valid, must match this pattern `{pattern}` since the docker container uses the same name.")
            return None
            
    # Validate pod URL
    error = StringUtils.is_valid_pat_url(t_pod_url)
    if error:
        st.warning(f"Invalid Tableau Online Server URL. {error}")
        return None
        
    # Check for existing tokens
    token_loader = TokenLoader(StreamLogger(st.container()))
    existing_token = token_loader.get_token_by_name(t_name, False)
    if existing_token:
        st.warning(f"token with name '{t_name}' already exists")
        return None
        
    # Check admin token limit for existing sites
    if t_name.startswith(ADMIN_PAT_PREFIX) and not new_site:
        existing_admin_pat = token_loader.get_token_admin_pat()
        if existing_admin_pat:
            st.warning(f"Token starting with `admin-pat` already exists. Only one admin token is needed.")
            return None
            
    # Create and validate token
    new_token = PatToken(t_name, t_secret, t_site_name, t_pod_url, t_comment)
    try:
        login_result = TableauCloudLogin.login(new_token, False)
    except Exception as ex:
        st.warning(f"Error logging in to Tableau Cloud APIs with token. {ex}")
        return None
    if not login_result.is_success:
        st.warning(f"INVALID PAT token '{t_name}'. Login to Tableau Cloud unsuccessful. {login_result.error}")
        return None

    # Verify site admin privileges
    logic = TCApiLogic(login_result)
    is_success, error = logic.does_token_have_site_admin_privileges()
    if not is_success:
        st.warning(f"PAT token is not SiteAdministrator. {error}")
        return None

    # Set additional info for admin tokens
    if new_token.is_admin_token():
        new_token.site_luid = login_result.site_luid
        session_info = logic.api.get_session_info() # Get session info for additional user details
        new_token.site_id = session_info['result']['site']['id']
        new_token.user_email = session_info['result']['user'].get('username')
        new_token.user_domain = session_info['result']['user'].get('domainName')

    logic.api.logout()
    return new_token


@st.dialog("🔑 Add Token", width="large")
def add_pat_token_dialog(bst: BridgeSiteTokens, token_loader):
    if not bst:
        bst = token_loader.load()
    link = PatToken.get_my_account_settings_link_markdown(bst.site.pod_url, bst.site.sitename, bst.site.user_domain, bst.site.user_email)
    st.info(f"Create Personal Access Tokens (PAT) from the Tableau Cloud {link} page. \n"
    f"- Add one PAT token starting with '{ADMIN_PAT_PREFIX}', for example 'admin-pat-1' or 'admin-pat-b' so that BridgeCTL can call Tableau Cloud APIs. \n"
    f"- Also add one PAT token for each bridge agent you wish to spin up in docker or kubernetes. These tokens can have any name. The bridge agent will be created with the same name as the selected token. Note that tokens starting with '{ADMIN_PAT_PREFIX}' cannot be used in bridge agents.\n"
    "- The PAT token should have SiteAdministrator permissions. \n"
    "- The tokens will be stored in `bridgectl/config/bridge_tokens.yml`")
    if len(bst.tokens) > 0:
        default_sitename = bst.site.sitename
        default_server_url = bst.site.pod_url
        new_site = st.columns([3,1])[1].checkbox("Add New Site", help=f"Check this box if you are adding a new Tableau Cloud Site (a site other than `{default_sitename}`)")
        if new_site:
            default_sitename = ""
            default_server_url = ""
    else:
        default_sitename = ""
        default_server_url = ""
        new_site = True

    with st.form(key="add_pat"):
        t_name = st.text_input("PAT Token Name", help="Name of PAT token")
        t_secret = st.text_input("PAT Token Secret")
        if new_site:
            sitename = st.text_input(
                "Tableau Cloud Site Name",
                value=default_sitename,
                help="Enter your Tableau Cloud site name (the part after 'https://10ay.online.tableau.com/#/site/')"
            )
        else:
            st.markdown(f"**Tableau Cloud Site Name:** 🌐 `{bst.site.sitename}`")
            sitename = bst.site.sitename
        t_site_name = sitename.lower() # some auth fails when site_name is uppercase.
        t_pod_url = st.text_input("Tableau Online Server URL", default_server_url, help="Tableau Online URL, for example `https://prod-useast-a.online.tableau.com`", disabled=not new_site)
        if st.form_submit_button("Add PAT"):
            with st.spinner(""):
                t_comment = ""
                new_token = validate_token(t_name, t_secret, t_site_name, t_pod_url, t_comment, new_site)
                if new_token:
                    if new_site and len(bst.tokens) > 0:
                        if t_site_name == bst.site.sitename:
                            st.warning(f"`{t_site_name}` is the same site. Please uncheck 'Add New Site'")
                            return
                        if token_loader.check_file_exists(t_site_name):
                            st.warning(f"tokens for site `{t_site_name}` already exists. Please use the 'Change site' dialog, then add more tokens for the site.")
                            return
                        token_loader.rename_token_file_to_site(bst.site.sitename)
                        token_loader.create_new()
                    token_loader.add_token(new_token)
                    st.session_state.show_toast = f"token {t_name} added"
                    st.rerun()

def format_token_name(token_s: PatTokenSecret):
    c = f"  ({token_s.comment})" if token_s.comment else ""
    return f"{token_s.name}{c}"

@st.dialog("🔑 Remove Token", width="large")
def remove_pat_token_dialog(bst: BridgeSiteTokens, token_loader: TokenLoader):
    if not bst:
        bst = token_loader.load()
    st.info("Select one or more PAT tokens to remove from `bridgectl/config/bridge_tokens.yml`")
    selected_token_names = st.multiselect("Select tokens to remove", bst.tokens, format_func= format_token_name, help="Select one or more tokens to remove")
    st.text("")
    st.text("")
    st.text("")
    st.text("")
    st.text("")
    st.text("")
    is_enabled = bool(selected_token_names)
    if st.button("Remove PAT", disabled=(not is_enabled)):
        removed_tokens = []
        for selected_token_name in selected_token_names:
            selected_token_name :PatTokenSecret = selected_token_name
            removed_tokens.append(selected_token_name.name)
            token_loader.remove_token(selected_token_name.name)
        st.session_state.show_toast = f"tokens removed: {', '.join(removed_tokens)}"
        st.rerun()

def validate_token_yaml(token_dict: dict, bst: BridgeSiteTokens):
    if "sitename" not in token_dict or not isinstance(token_dict["sitename"], str) or not token_dict["sitename"].strip():
        return "'sitename' is required and must be a non-empty string"
    if "server_url" not in token_dict or not isinstance(token_dict["server_url"], str) or not token_dict["server_url"].strip():
        return "'server_url' is required and must be a non-empty string"
    if "tokens" not in token_dict or not isinstance(token_dict["tokens"], list):
        return "'tokens' is required and must be a list"
    for index, item in enumerate(token_dict['tokens']):
        if "name" not in item:
            return f"'name' is required in tokens at index {index}"
        if "secret" not in item:
            return f"'secret' is required in tokens at index {index}"
    if bst.site.sitename and token_dict["sitename"] != bst.site.sitename:
        return f"site_name `{token_dict['sitename']}` does not match bridge_tokens.yml site_name `{bst.site.sitename}`, not importing."
    if bst.site.pod_url:
        if token_dict["server_url"] != bst.site.pod_url and f"https://{token_dict['server_url']}" != bst.site.pod_url:
            return f"server_url `{token_dict['server_url']}` does not match bridge_tokens.yml `{bst.site.pod_url}`, not importing."
    return None

def merge_token_yaml(logger, token_import_yml: str, token_loader: TokenLoader):
    if not os.path.exists(token_file_path):
        token_loader.create_new()
    bst = token_loader.load()
    token_dict = yaml.safe_load(token_import_yml)
    errors = validate_token_yaml(token_dict, bst)
    if errors:
        logger.warning(f"error validating import tokens: {errors}")
        return 0
    count_imported = 0
    if not bst.site.sitename:
        bst.site.sitename = token_dict["sitename"].lower()
    else:
        if bst.site.sitename.lower() != token_dict["sitename"].lower():
            logger.warning(f"site_name `{token_dict['sitename']}` does not match bridge_tokens.yml site_name `{bst.site.sitename}`, not importing.")
            return 0
    if not bst.site.pod_url:
        bst.site.pod_url = token_dict["server_url"]
    for item in token_dict["tokens"]:
        if token_loader.has_token_name(item["name"], bst.tokens):
            logger.warning(f"token with name `{item['name']}` already exists in bridge_tokens.yml, skipping.")
        else:
            pts = PatTokenSecret.from_dict(item)
            new_token = validate_token(pts.name, pts.secret, bst.site.sitename, bst.site.pod_url, "", new_site=False)
            if new_token:
                logger.info(f"token {pts.name} is valid")
                bst.tokens.append(pts)
                if new_token.is_admin_token():
                    bst.site.site_luid = new_token.site_luid
                    bst.site.site_id = new_token.site_id
                    bst.site.user_email = new_token.user_email
                    bst.site.user_domain = new_token.user_domain
                count_imported += 1
    if count_imported > 0:
        token_loader.save(bst)
    return count_imported

@st.dialog("🔑 Bulk Import PAT tokens", width="large")
def render_bulk_mode_dialog(bst: BridgeSiteTokens):
    form = st.form(key="import_settings")

    ext = f"You can manually create the tokens from the Tableau Cloud "
    ext += PatToken.get_my_account_settings_link_markdown(bst.site.pod_url, bst.site.sitename, bst.site.user_domain, bst.site.user_email)
    ext += " or use the [Tableau Bridge Config Helper](https://chromewebstore.google.com/detail/tableau-bridge-config-hel/pnghcjanlljbmedmaiapiipbmagpmlam) chrome extension"
    form.info(f"""To bulk Import PAT Tokens, please paste the following YAML format below. {ext}.\n
```
sitename: mysite123
server_url: prod-useast-a.online.tableau.com
tokens:
    - name: name1
      secret: aaa
    - name: name2
      secret: bbb
```   """)

    token_import_yaml = form.text_area("", height=250)
    cols_s1, cols_s2, cols_s3 = form.columns([1, 1, 3])
    if cols_s1.form_submit_button("Import"):
        if not token_import_yaml:
            st.warning("Please enter PAT tokens in valid YAML format")
            return
        logger = StreamLogger(form)
        token_loader = TokenLoader(logger)
        with st.spinner(""):
            count_imported = merge_token_yaml(logger, token_import_yaml, token_loader)
            if count_imported == 0:
                form.warning("No tokens imported")
            else:
                form.success(f"Imported {count_imported} tokens")
                st.page_link("src/page/5_Settings.py", label="Close")

@st.dialog("Change Tableau Cloud Site")
def show_change_site_dialog(token_loader: TokenLoader):
    st.info("BridgeCTL allows you to work with multiple Tableau Cloud sites. "
            "You can switch between sites by selecting a site from the dropdown below. "
            "You can add a new site from the Add Token dialog.")     #, help="This list is stored in the tokens_{sitename}.yml file in the bridgectl/config directory. You can add a new site by adding a PAT token for a different site."
    bst = token_loader.load()
    site_list = token_loader.get_token_yml_site_list()
    st.markdown(f"Current site name: `{bst.site.sitename}`")
    site_list = token_loader.get_token_yml_site_list()
    if not site_list:
        st.info("No other sites found. You can add additional sites by adding a Token and selecting 'Add New Site' checkbox.")
        return
    site_list.insert(0, bst.site.sitename)
    selected_site = st.selectbox("Change to Site:", site_list)
    is_disabled = selected_site == bst.site.sitename
    if st.button("Change Site", key="cng_site", disabled=is_disabled):
        # STEP: Swap bridge_tokens.yml files to be the currently selected file.
        token_loader.rename_token_file(bst.site.sitename, selected_site)
        st.success(f"Site changed to {selected_site}")
        sleep(1)
        st.rerun()
