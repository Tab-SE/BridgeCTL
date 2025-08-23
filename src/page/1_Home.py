import streamlit as st
from PIL import Image

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.shared_ui import SharedUi
from src.cli.app_config import APP_CONFIG, DeployEnviron
from src.models import AppSettings


def page_content():
    with st.container(border=True):
        col1, col2 = st.columns([2,1])
        
        with col1:
            st.markdown("### Build, Run, and Manage Tableau Bridge Containers")
            link = APP_CONFIG.readme_url()
            doc_link = f"[📚 Documentation]({link})"
            discussions_link = f"[💬 Discussions]({APP_CONFIG.discussions_url()})"
            st.markdown(f"{doc_link} • {discussions_link}")
        
        with col2:
            filename = "src/page/assets/tableau-bridge-2.png"
            image = Image.open(filename)
            st.image(image, width=170)

    # Features Section
    col1, col2 = st.columns([1,1])
    
    # Core Features
    app = AppSettings.load_static()
    with col1.container(border=True):
        st.markdown("### :material/check_circle: Core Features")
        show_feature("Build Bridge Linux Containers", ":material/build:", True)
        show_feature("Run and Manage Bridge Linux Containers in Local Docker", "🐳", True)
        show_feature("Health Monitoring with Slack/PagerDuty/NewRelic", ":material/monitor_heart:", True)
        show_feature("Search Bridge Logs & Troubleshoot", ":material/assignment:", True)
        show_feature("Publish Bridge Images to AWS ECR & Azure ACR", ":material/publish:", app.feature_aws_ecr_enabled or app.azure_acr_enabled)
        if app.dataconnect_feature_enable:
            show_feature("Publish Bridge Images to Data Connect Container Registry", ":material/publish:", app.dataconnect_feature_enable)

    # Developer Features
    with col2.container(border=True):
        st.markdown("### :material/rocket_launch: Enterprise Features")
        show_feature("Kubernetes Integration", ":material/grid_view:", app.feature_k8s_enabled)
        show_feature("Example Scripts to build your own Bridge Dockerfile", ":material/code:", app.feature_k8s_enabled)

        if APP_CONFIG.is_internal_build():
            st.markdown("### :material/developer_board: Developer Features")
            show_feature("Hammerhead EC2 Instance Management", "🦈", app.feature_hammerhead_enabled)

        st.markdown("<div style='text-align: center;'><a href='/Settings?tab=features'>⚙️ Configure Additional Features</a></div>", unsafe_allow_html=True)
    c1 = st.container(border=True)
    SharedUi.show_app_version(c1)
    st.write("")
    st.write("")



def show_feature(feature_name: str, icon, is_enabled: bool):
    if is_enabled:
        st.markdown(f"✅ {feature_name} {icon}")
    else:
        st.markdown(f"◻️ {feature_name} {icon}")


PageUtil.set_page_config(page_title="Home", page_header=":material/home: Tableau BridgeCTL")
page_content()

