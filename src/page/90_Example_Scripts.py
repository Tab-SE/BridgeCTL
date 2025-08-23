import streamlit as st

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.stream_logger import StreamLogger
from src.bridge_container_builder import buildimg_path
from src.bridge_dockerfile_web_builder import BridgeDockerfileWebBuilder
from src.bridge_rpm_tableau_com import BridgeRpmTableauCom
from src import bridge_settings_file_util
from src.driver_caddy.driver_script_generator import DriverDefLoader
from src.enums import LINUX_DISTROS, RunContainerAsUser
from src.lib.usage_logger import USAGE_LOG, UsageMetric
from src.models import BridgeRpmSource


def page_content():
    PageUtil.horizontal_radio_style()
    with st.expander("ℹ️ Instructions", expanded=False):
        st.info(
            "This page helps you create the necessary scripts for building and running Tableau Bridge containers:\n"
            "- Dockerfile: For building a custom Bridge container image\n" 
            "- Build Script: Shell script to build the container image\n"
            "- Run Script: Shell script to run Bridge containers\n"
            "- Kubernetes Script: commands for deploying Bridge to Kubernetes pods\n\n"
            "Note: You can edit the build parameters (base image, Linux distro, database drivers, etc.) on the Build Bridge page.\n"
        )

    # STEP - query_parameters
    req = bridge_settings_file_util.load_settings()

    is_w_bridge = True

    # Wrap the Parameters section in an expander
    # Create a container with border styling
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.markdown("#### Build Parameters")
        col2.page_link("src/page/10_Build_Bridge.py", label="Edit ✎", help="Edit the build parameters from the Build Bridge page.")
        # STEP - Base Image
        st.markdown(f"Base Image:`{req.bridge.base_image}` linux distro: `{req.bridge.linux_distro}`")
        drivers_list = ", ".join(req.bridge.include_drivers)
        st.markdown(f"Database Drivers: ```{drivers_list}```")
        u = RunContainerAsUser.tableau if req.bridge.user_as_tableau else RunContainerAsUser.root
        st.markdown(f"container runas user: `{u}`")

        # if is_w_bridge:
            # if req.bridge.bridge_rpm_source == BridgeRpmSource.devbuilds:
                # req.bridge.use_minerva_rpm = st.markdown("Use Minerva RPM", value=req.bridge.use_minerva_rpm, help="Check this box to use the new Minerva Bridge RPM, leave unchecked to use the stable DataServer Bridge RPM. Note the change to the download RPM url and start-bridgeclient.sh")
        if req.bridge.image_name_suffix:
            st.markdown(f"image name suffix: `{req.bridge.image_name_suffix}`")
        if req.bridge.locale:
            st.markdown(f"Locale: `{req.bridge.locale}`")

        # Close the border div
        st.markdown("</div>", unsafe_allow_html=True)

        # STEP - Latest Bridge RPM
        # col1, col2 = st.columns(2)
        sl = StreamLogger(st.container())
        if is_w_bridge:
            if req.bridge.bridge_rpm_source == BridgeRpmSource.devbuilds:
                from src.internal.devbuilds.bridge_rpm_download_devbuilds import BridgeRpmDownloadDevbuilds
                rpm_file_d, rpm_url = BridgeRpmDownloadDevbuilds(sl, buildimg_path).just_get_name_and_url_of_main_latest()
                st.markdown(f"Latest Bridge RPM from devbuilds: `{rpm_file_d}`")
            else:
                latest_rpm_file = BridgeRpmTableauCom.get_filename_from_version(BridgeRpmTableauCom.LATEST_RPM_VERSIONS[0])
                st.markdown(f"Latest Bridge RPM from tableau.com: `{latest_rpm_file}`")
    col_s1, col_s2 = st.columns(2)
    if col_s1.button("Generate Scripts"):
        builder = BridgeDockerfileWebBuilder(sl, req)
        (dockerfile_contents, start_contents, build_sh_contents,
            download_contents, download_drivers_contents, install_drivers_contents, run_bridge_contents) = builder.generate_dockerfile()
        
        # Generate kubectl run command
        kubectl_run_cmd = builder.generate_kubectl_run_cmd()
        
        if is_w_bridge:
            st.markdown("#### Dockerfile")
            st.code(dockerfile_contents, language="text")
            st.markdown("#### start-bridgeclient.sh")
            st.code(start_contents, language="text")
            st.markdown("#### docker build command")
            st.code(build_sh_contents, language="text")
            st.markdown("#### bridge rpm download")
            st.code(download_contents, language="text")
        st.markdown("#### download_drivers.sh")
        st.code(download_drivers_contents, language="text")
        st.markdown("#### install_drivers.sh")
        st.code(install_drivers_contents, language="text")
        if is_w_bridge:
            st.markdown("#### Run a bridge agent container in Local Docker")
            st.code(run_bridge_contents, language="bash")
            
            # Add kubectl run command
            st.markdown("#### Run a bridge agent container in Kubernetes")
            st.code(kubectl_run_cmd, language="bash")
            
        USAGE_LOG.log_usage(UsageMetric.example_scripts_show)

    # STEP - Show Param Link
    st.markdown("")


PageUtil.set_page_config("Example Bridge Scripts", ":material/code: Example Scripts for Tableau Bridge Containers")
page_content()
