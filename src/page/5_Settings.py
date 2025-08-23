from time import sleep
import re

import streamlit as st
import streamlit.components.v1 as components

from src.page.ui_lib.login_manager import LoginManager
from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.pat_tokens_ui import add_pat_token_dialog, remove_pat_token_dialog, show_change_site_dialog, \
    render_bulk_mode_dialog
from src.page.ui_lib.shared_bridge_settings import show_k8s_context
from src.page.ui_lib.shared_ui import SharedUi
from src.page.ui_lib.stream_logger import StreamLogger
from src.cli import version_check
from src.cli.app_config import APP_CONFIG, APP_NAME_FOLDER
from src.ecr_registry_private import EcrRegistryPrivate
from src.enums import ADMIN_PAT_PREFIX, LOCALHOST
from src.github_version_checker import GithubVersionChecker
from src.k8s_client import K8sSettings, K8sClient
from src.lib.general_helper import FileHelper, StringUtils
from src.lib.usage_logger import USAGE_LOG, UsageMetric
from src.models import AppSettings
from src.token_loader import TokenLoader


def render_auth_tokens_tab(tab):
    tab.subheader("Tableau Cloud Token Authentication")
    tab.info(f"Bridge Linux uses Personal Access Tokens to authenticate to Tableau Cloud. See [Tableau Cloud Documentation - Personal Access Tokens](https://help.tableau.com/current/server/en-us/security_personal_access_tokens.htm)."
             f"\nNote that BridgeCTL can manage bridge agents for one or multiple Tableau Cloud sites. See the Add Token dialog for details. ")
    # STEP - Show tokens and warnings
    token_loader = TokenLoader(StreamLogger(st.container()))
    bst = token_loader.load()
    token_names = [x.name for x in bst.tokens]
    c1,c2 = tab.columns([2, 3])
    if bst.site.sitename:
        c1.markdown(f"### 🌐 Site: `{bst.site.sitename}`")

        # c1.markdown(f"Tokens added for site 🌐 `{bst.site.sitename}`")
        if c2.button(":material/swap_horiz: Change Site"):
            show_change_site_dialog(token_loader)
        tokens_display = ', '.join([f"{t.name}" for t in bst.tokens])
        tab.markdown(f"#### 🔑 Tokens Added: `{tokens_display}`", help=f"These tokens are stored in the `bridgectl/config/bridge_tokens.yml`")
    have_admin_pat =  any(t.startswith(ADMIN_PAT_PREFIX) for t in token_names)
    if not have_admin_pat:
        tab.warning(f"Note: You have not yet added a Token starting with '{ADMIN_PAT_PREFIX}'.")
    else:
        have_bridge_token = any(not t.startswith(ADMIN_PAT_PREFIX) for t in token_names)
        if not have_bridge_token:
            tab.warning(f"Note: You have not yet added a PAT Token that does NOT start with '{ADMIN_PAT_PREFIX}', this token will be used to run a Bridge agent. This token can have any name you choose.")

    # STEP - Show Add button
    ct1, ct2 = tab.columns([2,3])
    if ct1.button("Add Token"):
        add_pat_token_dialog(bst, token_loader)
    if ct2.button("Bulk Import"):
        render_bulk_mode_dialog(bst)
    if tab.button("Remove Token"):
        remove_pat_token_dialog(bst, token_loader)

def get_uploader_key():
    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0
    return st.session_state["file_uploader_key"]

def validate_k8s_namespace(namespace, col1):
    if not namespace:
        col1.warning("Namespace is required")
        return False
    pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
    if not re.match(pattern, namespace):
        col1.text(f"Invalid namespace. Must match pattern: {pattern}")
        return False
    return True


def render_k8s_tab(tab_k8s, app: AppSettings):
    tab_k8s.subheader("Kubernetes Configuration")
    
    # Kubernetes Configuration Section
    config_container = tab_k8s.container(border=True)
    is_k8s_enabled = config_container.checkbox(
        "Enable Kubernetes integration",
        app.feature_k8s_enabled,
        help="Enable Kubernetes integration to deploy Bridge agents as pods in your cluster."
    )
    if app.feature_k8s_enabled != is_k8s_enabled:
        app.feature_k8s_enabled = is_k8s_enabled
        app.save()
        st.rerun()    
    if not app.feature_k8s_enabled:
        return

    col1, col2 = config_container.columns([2, 1])
    
    if K8sSettings.does_kube_config_exist():
        col1.success(f"✓ Valid kube_config found at: `{K8sSettings.kube_config_path}`")
        if not show_k8s_context(config_container, False):
            return
        if config_container.button("Edit Namespace"):
            show_edit_namespace_dialog(app)
        if config_container.button("Test Connection"):
            k8s_client = K8sClient()
            status = k8s_client.check_connection()
            if status.can_connect:
                config_container.success("✓ Successfully connected to Kubernetes cluster")
            else:
                config_container.error(f"❌ Failed to connect to Kubernetes cluster: {status.error}")

    if col2.button("Change kube_config", use_container_width=True):
        show_upload_kube_config_dialog()

@st.dialog("Upload Kubernetes Config", width="large")
def show_upload_kube_config_dialog():
    st.info("To authenticate to your kubernetes cluster, please upload the kube config yaml file. "
            "This will be stored at ~/.kube/config." + 
            (" The current kube config file will be backed up to ~/.kube/config.bak" 
             if K8sSettings.does_kube_config_exist() else ""))
    
    uploaded_file = st.file_uploader(
        'Upload kube config file',
        accept_multiple_files=False,
        key="kube_config_uploader"
    )
    
    if uploaded_file is not None:
        value = uploaded_file.getvalue()
        error_msg = FileHelper.validate_yaml(value)
        if error_msg:
            st.warning(f"Invalid yaml file. Error:\n\n{error_msg}")
        else:
            K8sSettings.backup_kube_config()
            K8sSettings.save_kube_config(value)
            st.success("✓ Kube config file uploaded successfully")
            sleep(1)
            st.rerun()

@st.dialog("Edit Namespace", width="medium")
def show_edit_namespace_dialog(app: AppSettings):
    st.info("Enter the namespace where Tableau Bridge pods will be deployed. The namespace must exist in your cluster.")
    
    selected_namespace = st.text_input(
        "Target namespace",
        app.k8s_namespace,
        help="The namespace must follow Kubernetes naming conventions (lowercase letters, numbers, and hyphens)."
    )
    
    if st.button("Save", use_container_width=True):
        if validate_k8s_namespace(selected_namespace, st):
            app.k8s_namespace = selected_namespace
            app.save()
            st.success("✓ Kubernetes namespace saved")
            sleep(.7)
            st.rerun()

def save_ecr_settings(form, app, account_id, repo_name, aws_region, aws_profile):
    pattern_id = r'^\d{12}$' # Regular expression to match a 12-digit number
    if not re.match(pattern_id, str(account_id)):
        form.warning("AWS Account ID must be 12 digits")
        return
    pattern_repo = r'^[a-z]([a-z0-9\-_./]{0,254}[a-z0-9])?$' # Regular expression to match the repository name rules
    if not(2 <= len(repo_name) <= 256 and re.match(pattern_repo, repo_name)): # Ensure length is within the valid range and match pattern
        form.warning(f"Repository Name should match `{pattern_repo}`")
        return
    pattern_region = r'^[a-z]{2}-[a-z]+-\d$'
    if not re.match(pattern_region, aws_region):
        form.warning(f"Region must match '{pattern_region}'")
        return
    pattern = r"^[a-zA-Z0-9._-]{1,128}$"
    if aws_profile and re.match(pattern, aws_profile):
        form.warning("Profile must be alphanumeric or blank")
        return
    if (account_id == app.ecr_private_aws_account_id and repo_name == app.ecr_private_repository_name
            and aws_region == app.aws_region and aws_profile == app.aws_profile):
        form.warning("No change")
        return

    app.ecr_private_aws_account_id = account_id
    app.ecr_private_repository_name = repo_name
    app.aws_region = aws_region
    app.aws_profile = aws_profile
    app.save()
    form.success("ECR settings saved")
    sleep(2)
    st.rerun()

def save_acr_settings(form2, app, subscription_id, resource_group, acr_name):
    if not subscription_id:
        form2.warning("Subscription ID is required")
        return
    if not resource_group:
        form2.warning("Resource Group is required")
        return
    if not acr_name:
        form2.warning("ACR Name is required")
        return
    if (subscription_id == app.azure_acr_subscription_id and resource_group == app.azure_acr_resource_group
            and acr_name == app.azure_acr_name):
        form2.warning("No change")
        return
    app.azure_acr_subscription_id = subscription_id
    app.azure_acr_resource_group = resource_group
    app.azure_acr_name = acr_name
    app.save()
    form2.success("ACR Settings saved")
    sleep(2)
    st.rerun()

@st.dialog("Edit Remote Host", width="large")
def show_dialog_remote_host_edit(app):
    ma = st.text_input("Remote Host", app.repository_remote_machine_address, help="Enter the remote host")
    sp = st.text_input(f"Remote Host ssh pem path: ", app.repository_remote_machine_ssh_path, help="Enter the path to the ssh pem file")
    if st.button("Save", disabled = ma == app.repository_remote_machine_address and sp == app.repository_remote_machine_ssh_path):
        app.repository_remote_machine_address = ma
        app.repository_remote_machine_ssh_path = sp
        app.save()
        st.success("Remote Host saved")
        sleep(2)
        st.rerun()

def render_container_registry_tab(tab_registry, app: AppSettings):
    tab_registry.subheader("Container Registry")
    col1, col2, col3 = tab_registry.columns(3)
    col1.markdown("#### AWS ECR Repository")
    is_ecr_enabled = col1.checkbox("Enable AWS ECR", app.feature_aws_ecr_enabled, help="Enable AWS Private Elastic Container Registry integration.")
    if app.feature_aws_ecr_enabled != is_ecr_enabled:
        app.feature_aws_ecr_enabled = is_ecr_enabled
        app.save()
        st.rerun()
    if app.feature_aws_ecr_enabled:
        col1.info("Instructions: Enter the information about your private AWS ECR repository. "
                  "You can find the URI of your Private ECR Repository in the [AWS ECR Console](https://us-west-2.console.aws.amazon.com/ecr/private-registry/repositories). \n\n"
                  "Example: *123456789012.dkr.ecr.us-west-2.amazonaws.com/my-repository*, where *123456789012* is the AWS AccountID and *my-repository* is the ECR Repository name.\n\n"
                  "Note that in order to use ECR, you need to have the [AWS CLI](https://aws.amazon.com/cli) installed locally and configured with the correct [authentication credentials](https://stackoverflow.com/questions/44243368/how-to-login-with-aws-cli-using-credentials-profiles).")
        form = col1.form(key="cont_reg")
        account_id = StringUtils.val_or_empty(form.text_input("AWS AccountID", app.ecr_private_aws_account_id))
        repo_name = StringUtils.val_or_empty(form.text_input("Private ECR Repository Name", app.ecr_private_repository_name))
        aws_region = StringUtils.val_or_empty(form.text_input("AWS Region", app.aws_region))
        aws_profile = form.text_input("Profile", app.aws_profile if app.aws_profile else "default", help="AWS Profile used in .aws/credentials, for example 'saml'. Leave blank for default profile.")
        reg = EcrRegistryPrivate(StreamLogger(form), account_id, repo_name, aws_region, aws_profile)
        console_url = reg.get_aws_console_url()
        form.markdown(f"Full URL: `{reg.get_repo_url()}` [browse]({console_url})")
        if form.form_submit_button("Save"):
            save_ecr_settings(form, app, account_id, repo_name, aws_region, aws_profile)
        if col1.button("Validate Connection to ECR"):
            is_success, error = reg.check_connection_to_ecr() #FutureDev: make error message better
            if is_success:
                col1.success("Connection to ECR successful")
            else:
                col1.error(f"Error: {error}")

    col2.markdown("#### Azure Image Repository")
    azure_registry_enabled = col2.checkbox("Enable Azure Container Registry", app.azure_acr_enabled, help="Enable Azure Container Registry integration.")
    if app.azure_acr_enabled != azure_registry_enabled:
        app.azure_acr_enabled = azure_registry_enabled
        app.save()
        st.rerun()
    if app.azure_acr_enabled:
        col2.info(
            "Instructions: Enter the information about your private Azure Container Registry (ACR). "
            "You can find your ACR details in the [Azure Portal](https://portal.azure.com/). \n\n"
            "Example: *myregistry.azurecr.io*, where *myregistry* is the ACR name. "
            "You also need your Subscription ID and Resource Group name."
        )
        form2 = col2.form(key="cont_reg_azure")
        subscription_id = StringUtils.val_or_empty(
            form2.text_input("Azure Subscription ID", app.azure_acr_subscription_id)
        )
        resource_group = StringUtils.val_or_empty(
            form2.text_input("Resource Group", app.azure_acr_resource_group)
        )
        acr_name = StringUtils.val_or_empty(
            form2.text_input("Azure ACR Name", app.azure_acr_name)
        )
        # azure_profile = form2.text_input("Azure CLI Profile", app.azure_profile if app.azure_profile else "default",help="Azure CLI Profile, for example 'default'")
        # reg2 = AcrRegistry(
        #     subscription_id, resource_group, acr_name, acr_login_server, azure_profile
        # )

        # console_url = reg2.get_aws_console_url()
        # form2.markdown(f"Full URL: `{reg2.get_repo_url()}` [browse]({console_url})")

        if form2.form_submit_button("Save"):
            save_acr_settings(form2, app, subscription_id, resource_group, acr_name)
        # if col2.button("Validate Connection to Azure ACR"):
        #     is_success, error = reg2.check_connection_to_acr()  # FutureDev: make error message better
        #     if is_success:
        #         col2.success("Connection to ACR successful")
        #     else:
        #         col2.error(f"Error: {error}")
    if APP_CONFIG.is_internal_build() and False:
        col3.markdown("#### Remote Host via SSH")
        is_remote_host_enabled = col3.checkbox("Enable Remote Host via SSH", app.repository_remote_machine_enabled, help="Enable Remote Machine")
        col3.info("Connect to a remote machine via SSH to push images to a remote local docker registry.")
        if app.repository_remote_machine_enabled != is_remote_host_enabled:
            app.repository_remote_machine_enabled = is_remote_host_enabled
            app.save()
            st.rerun()
        if app.repository_remote_machine_enabled:
            col3.markdown(f"Remote Host: `{app.repository_remote_machine_address}`")
            col3.markdown(f"Remote Host ssh pem path: `{app.repository_remote_machine_ssh_path}`")
            if col3.button("Edit"):
                show_dialog_remote_host_edit(app)


def render_updates_tab(tab_updates):
    tab_updates.subheader("App Updates")
    col1, col2 = tab_updates.columns(2)
    release_notes_url = APP_CONFIG.release_notes_url()
    space = "&nbsp;" * 50
    col1.info(f"Current BridgeCTL version: {APP_CONFIG.app_version} {space} [release notes]({release_notes_url})")
    c1 = tab_updates.container(border=True)
    SharedUi.show_app_version(c1, True)

    if col1.button(f"Check for App Updates"):
        check_for_app_updates_dialog()
    tab_updates.markdown("")

@st.dialog("Check for App Updates", width="large")
def check_for_app_updates_dialog():
    cont = st.container(border=True)
    url = GithubVersionChecker.get_releases_home()
    cont.write(f"Checking for newer [bridgectl release]({url})")
    with st.spinner(""):
        latest_ver_msg, latest_ver = version_check.check_latest_and_get_version_message()
    latest_ver_msg = latest_ver_msg.replace("[green]", "").replace("[/green]", "").replace("[red]", "").replace(
        "[/red]", "").replace("[blue]", "").replace("[/blue]", "")
    cont.text(f"Latest version: {latest_ver} \n\n {latest_ver_msg}")
    if "new version" in latest_ver_msg:
        cont.text(f"To update, run `{APP_NAME_FOLDER}` from the command-line")
    USAGE_LOG.log_usage(UsageMetric.settings_chk_updates)


def render_features_tab(tab_features, app: AppSettings):
    tab_features.subheader("Features")
    
    # Main info section
    tab_features.info("""
        Configure which features are enabled in BridgeCTL. For Kubernetes and Container Registry features, see those tabs respectively.
    """)
    
    # Create containers for different feature groups
    basic_features = tab_features.container(border=True)
    # basic_features.markdown("#### Basic Features")
    
    # Example Scripts Feature
    col1, col2 = basic_features.columns([1, 3])
    enable_example = col1.checkbox(
        "Example Scripts", 
        value=app.feature_example_scripts_enabled,
        key="feature_example_scripts"
    )
    col2.markdown("Shows example bash scripts for building and running bridge containers.")
    
    if app.feature_example_scripts_enabled != enable_example:
        app.feature_example_scripts_enabled = enable_example
        app.save()
        st.rerun()

    if APP_CONFIG.is_internal_build():
        enable_dataconnect = col1.checkbox(
            "DataConnect", 
            value=app.dataconnect_feature_enable,
            key="feature_dataconnect"
        )
        col2.markdown("Build and publish container base images to the Data Connect Container Registry. :material/lock: (internal only)")
        if app.dataconnect_feature_enable != enable_dataconnect:
            app.dataconnect_feature_enable = enable_dataconnect
            app.save()
            st.rerun()

        advanced_features = tab_features.container(border=True)
        advanced_features.markdown("#### Developer Features")
        
        # Hammerhead Features
        col1, col2 = advanced_features.columns([1, 3])
        enable_hammerhead_features = col1.checkbox(
            "Hammerhead", 
            value=app.feature_hammerhead_enabled,
            key="feature_hammerhead"
        )
        col2.markdown("Provides tools to report and modify your Hammerhead EC2 instances. :material/lock: (internal only)")
        
        if enable_hammerhead_features and app.streamlit_server_address != LOCALHOST:
            advanced_features.warning("⚠️ Hammerhead can only be enabled when streamlit_server_address = 'localhost'")
            enable_hammerhead_features = False
            
        if app.feature_hammerhead_enabled != enable_hammerhead_features:
            app.feature_hammerhead_enabled = enable_hammerhead_features
            app.save()
            st.rerun()


def render_ui_tab(tab_ui, app: AppSettings):
    tab_ui.subheader("User Interface")
    app.monitor_slack_api_key
    cont_a = tab_ui.columns(2)[0].container(border=True)
    cont_a.markdown("#### URL")
    u = f"{app.streamlit_server_address}:8505"
    h = f"You can edit the User Interface address from the `bridgectl` command-line. Select the menu __Edit UI Service Settings__-> __Edit User Interface address__"
    cont_a.markdown(f"User Interface address: __{u}__", help=h)
    cont = tab_ui.columns(2)[0].container(border=True)
    LoginManager.update_login(app, cont)

def show_toast_after_refresh():
    if 'show_toast' in st.session_state and st.session_state.show_toast:
        st.toast(str(st.session_state.show_toast))
        st.session_state.show_toast = False

def select_tab_from_query_param():
    """
    Look-up the tab from the query-string and click that tab
    """
    query_param = st.query_params.get("tab")
    if not query_param:
        return
    tab_mapping = {
        "tokens": 0,
        "k8s": 1,
        "registry": 2,
        "features": 3,
        "updates": 4
    }
    # ref: https://discuss.streamlit.io/t/how-to-bring-the-user-to-a-specific-tab-within-a-page-in-my-multipage-app-using-the-url/42796/7
    index_tab = tab_mapping.get(query_param)
    js = f"""
    <script>
        var tab = window.parent.document.getElementById('tabs-bui1-tab-{index_tab}');
        tab.click();
    </script>
    """
    if index_tab:
        components.html(js) # ref: https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v1.html

def render_system_test_tab(tab_system_test):
    system_test_cmd = "docker run --rm --platform linux/amd64 registry.hub.docker.com/redhat/ubi9:latest uname -m"
    tab_system_test.info(
        f"Tableau Bridge requires amd64 compatible architecture to run. To verify that your system can build and run amd64 images "
        f"this test will execute the following command which will download and run the latest Redhat9 image with platform: linux/amd64. The test takes just a few seconds to complete. It will also verify that docker is properly installed.\n\n"
        f" `{system_test_cmd}`\n\n"
        f" If the test fails, you may need to enable amd64 virtualization or use a different machine.")
    with tab_system_test:
        if st.button("Run Docker Build System Test"):
            with st.spinner("Running System Test"):
                from src.subprocess_util import SubProcess
                stdout, stderr, return_code = SubProcess.run_cmd_light(system_test_cmd)
                st.text(f"stdout: {stdout}")
                if stderr:
                    st.text(f"stderr: {stderr}")
                if return_code == 0:
                    st.success("System Test Passed")
                if return_code != 0:
                    st.error(f"Error running System Test.")

@st.dialog("Thank You for Using Tableau BridgeCTL! 🚀", width="large")
def show_feedback_dialog(app: AppSettings):
    with st.container(border=True):
        st.info(
            "We're constantly working to improve BridgeCTL and make it more useful for users like you. "
            "Your feedback helps us prioritize features and improvements."
        )
        
        st.markdown("#### We'd Love to Hear About:")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            - Features you find most valuable
            - Pain points or challenges
            - Missing features you'd like to see
            """)
        with col2:
            st.markdown("""
            - Usability improvements
            - Documentation clarity
            """)
    
    # Call to action section
    g = "User Feedback" if APP_CONFIG.is_internal_build() else "GitHub Discussions"
    st.html(
        "<div style='text-align: center; margin: 30px 0;'>"
        f"<div style='text-align: center;'><a href='{APP_CONFIG.discussions_url()}' "
        f" target='_blank' rel='noopener noreferrer' style='text-decoration: none;'>"
        f"<div style='background-color: #0066cc; color: white; padding: 15px 30px; "
        f"border-radius: 5px; display: inline-block; font-size: 18px;'>"
        f"💬 Join the Discussion on {g}</div></a></div>"
        "</div>"
    )

    # Dismiss option
    st.divider()
    dismiss = st.checkbox("Don't show this dialog again", help="You can always provide feedback through the Discussions link on the Home page")
    if dismiss != app.dismiss_initial_feedback_dialog:
        app.dismiss_initial_feedback_dialog = dismiss
        app.save()

def page_content():
    app = AppSettings.load_static()
    if not app.dismiss_initial_feedback_dialog:
        show_feedback_dialog(app)
        
    tab_pats, tab_k8s, tab_registry, tab_features, tab_updates, tab_ui, tab_system_test = st.tabs(["Token Authentication", "Kubernetes", "Container Registry", "Features", "App Updates", "User Interface", "System Test"])
    show_toast_after_refresh()
    render_auth_tokens_tab(tab_pats)
    render_k8s_tab(tab_k8s, app)
    render_container_registry_tab(tab_registry, app)
    render_features_tab(tab_features, app)
    render_updates_tab(tab_updates)
    render_ui_tab(tab_ui, app)
    render_system_test_tab(tab_system_test)
    select_tab_from_query_param()

PageUtil.set_page_config(page_title="Settings", page_header=":material/settings: Settings")
page_content()

