import os
from time import sleep

import streamlit as st

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.shared_bridge_settings import show_unc_path_mappings, show_image_created, render_image_details
from src.page.ui_lib.stream_logger import StreamLogger
from src.bridge_container_builder import BridgeContainerBuilder, buildimg_path, bridge_client_config_path, BRIDGE_BUILD_STATE
from src.bridge_rpm_download import BridgeRpmDownload
from src.bridge_rpm_tableau_com import BridgeRpmTableauCom
from src import bridge_settings_file_util
from src.cli.app_config import APP_CONFIG
from src.docker_client import DockerClient
from src.driver_caddy.driver_script_generator import DriverDefLoader, DriverDef, DriverScriptGenerator
from src.driver_caddy.ui_driver_definition import UiDriverDefinition
from src.enums import LINUX_DISTROS, RunContainerAsUser, PropNames, locale_list, DEFAULT_DOCKER_NETWORK_MODE, \
    VALID_DOCKER_NETWORK_MODES
from src.lib.usage_logger import USAGE_LOG, UsageMetric
from src.models import AppSettings, BridgeRpmSource, BridgeImageName, BridgeRequest
from src.validation_helper import ValidationHelper


def save_settings(db_drivers, bridge_rpm_source, use_minerva_rpm, base_image, user_as_tableau, linux_distro, image_name_suffix, rpm_version_tableau, locale, bridge_rpm_version_devbuilds_is_specific, rpm_version_devbuilds):
    req = bridge_settings_file_util.load_settings()
    req.bridge.include_drivers = db_drivers
    req.bridge.bridge_rpm_source = bridge_rpm_source
    req.bridge.base_image = base_image
    req.bridge.linux_distro = linux_distro
    req.bridge.user_as_tableau = user_as_tableau
    req.bridge.image_name_suffix = image_name_suffix
    req.bridge.locale = locale
    if req.bridge.bridge_rpm_source == BridgeRpmSource.tableau_com:
        req.bridge.bridge_rpm_version_tableau_com = rpm_version_tableau
    else:
        req.bridge.bridge_rpm_version_devbuilds_is_specific = bridge_rpm_version_devbuilds_is_specific
        if bridge_rpm_version_devbuilds_is_specific:
            req.bridge.bridge_rpm_version_devbuilds = rpm_version_devbuilds
    if use_minerva_rpm is not None:
        req.bridge.use_minerva_rpm = use_minerva_rpm
    bridge_settings_file_util.save_settings(req)

@st.dialog("Accept Database Driver EULA", width="large")
def show_dialog_accept_db_eula(req):
    st.markdown("I acknowledge that the database driver install scripts provided here are examples only. "
                "I acknowledge that I have written my own database drive install scripts customized to my particular company "
                "needs and security policies. I acknowledge that I am in compliance with the database driver vendor terms of service. "
                "When required by the database driver vendor, I have accepted the database driver vendor's end user license agreement (EULA) on their respective "
                "websites and downloaded the driver from their website.")
    if st.button("Accept"):
        req.bridge.db_driver_eula_accepted = True
        bridge_settings_file_util.save_settings(req)
        st.success("Driver EULA Accepted")
        sleep(.7)
        st.rerun()

def check_for_local_drivers(req: BridgeRequest) -> list[tuple[str, str]]:
    """
    Check for drivers that require manual download and return a list of tuples containing
    (driver_name, error_message) for each missing driver.
    """
    driver_generator = DriverScriptGenerator(StreamLogger(st.container()), buildimg_path)
    pre_post_scripts, drivers_def = driver_generator.driver_loader.load_driver_defs()
    if not drivers_def:
        return []
        
    missing_drivers = []
    for driver in drivers_def:
        if driver['driver'] in req.bridge.include_drivers:
            driver_def = DriverDef(**driver)
            error_msg = driver_generator.validate_local_driver(driver_def)
            if error_msg:
                missing_drivers.append((driver['driver'], error_msg))
    
    return missing_drivers

def page_content():
    PageUtil.horizontal_radio_style()
    st.info(f"""Select database drivers and enter a base image.
A local docker image will be created. Note that a Dockerfile and the required files will be copied to the folder `buildimg` which you can further customize if needed.
""")
    req = bridge_settings_file_util.load_settings()
    st.markdown("#### Build Parameters")
    colv_1, colv_2 = st.columns([2, 1])
    colv_1.markdown(f"Base Image:`{req.bridge.base_image}` linux distro: `{req.bridge.linux_distro}`")
    drivers_list = ", ".join(req.bridge.include_drivers)
    colv_1.markdown(f"Database Drivers: ```{drivers_list}```")
    if colv_2.button("Edit ✎"):
        edit_build_parameters_dialog(req)
    with colv_2.expander("more parameters "):
        st.text("")
        st.text("")
        c1, c2 = st.columns([1,1])
        if c1.button("Import Driver Definition File"):
            UiDriverDefinition.define_drivers(req)
        if c2.button("Upload Drivers"):
            UiDriverDefinition.upload_driver_setup_files()
        # if APP_CONFIG.is_internal_build():
        if st.button("Define UNC File Path Mappings"):
            edit_unc_path_mappings_dialog(req)
        if st.button("Define Container DNS Mappings"):
            show_edit_dns_mapping_dialog(req)

    if req.bridge.only_db_drivers:
        colv_1.markdown("only build base image with drivers (skip bridge rpm): `true`")
    else:
        if req.bridge.bridge_rpm_source == BridgeRpmSource.devbuilds:
            brd = BridgeRpmDownload(colv_1, req.bridge.bridge_rpm_source, buildimg_path)
            if req.bridge.bridge_rpm_version_devbuilds_is_specific:
                is_downloaded = brd.is_rpm_filename_already_downloaded(req.bridge.bridge_rpm_version_devbuilds)
                r = req.bridge.bridge_rpm_version_devbuilds
                r += " (already downloaded)" if is_downloaded else " (will be downloaded)"
            else:
                rpm_downloaded = brd.get_rpm_filename_already_downloaded()
                r = rpm_downloaded if rpm_downloaded else "(latest rpm will be downloaded from devbuild/main)"

            colv_1.markdown(f"Bridge RPM: `{r}` _devbuilds_")
            cols = colv_1.columns([1, 1])
            cols[1].markdown(f"Use Minerva: `{req.bridge.use_minerva()}`")
        else:
            ver = req.bridge.bridge_rpm_version_tableau_com if req.bridge.bridge_rpm_version_tableau_com else BridgeRpmTableauCom.LATEST_RPM_VERSIONS[0]
            cols = colv_1.columns([1, 1])
            cols[0].markdown(f"Bridge RPM: `{BridgeRpmTableauCom.get_filename_from_version(ver)}`")
            cols[1].markdown(f"Use Minerva: `{req.bridge.use_minerva()}`", help="Minerva is the new bridge agent runtime available in version 2024.3 and later [see docs](https://help.tableau.com/current/online/en-us/to_bridge_linux_install.htm). Minerva is started using bin/run-bridge.sh instead of bin/TabBridgeClientWorker")

    u = RunContainerAsUser.tableau if req.bridge.user_as_tableau else RunContainerAsUser.root
    colv_1a, colv_1b, col1v_1c = colv_1.columns(3)
    colv_1a.markdown(f"container runas user: `{u}`")
    if req.bridge.image_name_suffix:
        colv_1b.markdown(f"image name suffix: `{req.bridge.image_name_suffix}`")
    if req.bridge.locale:
        col1v_1c.markdown(f"Locale: `{req.bridge.locale}`")
    show_unc_path_mappings(req, colv_1b)
    if req.bridge.dns_mappings:
        dns_list = ""
        for k,v in req.bridge.dns_mappings.items():
            dns_list += f"  {k} => {v}\n"
        dns_help = f"Container DNS Mappings to add to the /etc/hosts file inside the bridge container:\n\n {dns_list}"
        colv_1b.markdown(f"DNS Mappings: `{len(req.bridge.dns_mappings)}`", help=dns_help)
    if bridge_client_config_path.exists():
        colv_1.markdown(f"Use custom Bridge client configuration: `yes`", help= f"Client configuration file will be copied to the container image from this location {bridge_client_config_path}.")
    
    if req.bridge.docker_network_mode and req.bridge.docker_network_mode != DEFAULT_DOCKER_NETWORK_MODE:
        colv_1.markdown(f"Container Network Mode: `{req.bridge.docker_network_mode}`", help="The network mode that will be used when running the container.")

    # if not APP_CONFIG.is_internal_build():
    #     if not req.bridge.db_driver_eula_accepted:
    #         colv_2.warning("Please accept the database driver EULA before building the image.")
    #         if colv_2.button("Accept Driver EULA"):
    #             show_dialog_accept_db_eula(req)
    docker_client = DockerClient(StreamLogger(st.container()))
    if not docker_client.is_docker_available():
        st.stop()
    if colv_1.button("Build Image"): #, disabled = not req.bridge.db_driver_eula_accepted):
        show_start_build_dialog(req)
    else:
        st.write("---")
    cb1, cb2 = st.columns([2,1])
    cb1.markdown("#### Built Image Details")
    img_detail = docker_client.get_image_details(BridgeImageName.local_image_name(req))
    if img_detail is None:
        imn = BridgeImageName.local_image_name(req)
        if "_version_unknown" in imn:
            cb1.caption(f"not yet built")
        else:
            cb1.write(f"No image yet labeled *{imn}*")
    else:
        cont = cb1.container(border=True)
        cont.markdown(f"Local Image Name: *{img_detail.image_name}*  :material/check:")
        show_image_created(cont, img_detail)
        render_image_details(cont, docker_client, img_detail.image_name, img_detail)

@st.dialog("Build Bridge Image", width="large")
def show_start_build_dialog(req: BridgeRequest):
    cont_b = st.empty()
    if not cont_b.button("Start Build", disabled = BRIDGE_BUILD_STATE.is_building, key="btnStartBuild"):
        if BRIDGE_BUILD_STATE.is_building:
            st.warning("Another build is in progress. Please wait for it to finish.")
            return
        if "mysql" in req.bridge.include_drivers and not req.bridge.locale:
            st.warning("MySQL driver requires locale libraries to work correctly. Please select a locale.")
        missing_drivers = check_for_local_drivers(req)
        if missing_drivers:
            warning_msg = "⚠️ The following drivers require manual download:\n\n"
            for driver, error in missing_drivers:
                warning_msg += f"- {error}\n"
            st.warning(warning_msg)
        if req.bridge.unc_path_mappings and req.bridge.bridge_rpm_source == BridgeRpmSource.tableau_com and  req.bridge.bridge_rpm_version_tableau_com < "20251":
            warning_msg = "⚠️ UNC Mappings have been defined but only Tableau Bridge 2025.1 and greater support UNC Mappings:\n\n"
            st.warning(warning_msg)
        st.info("Build the Tableau Bridge container image. This may take a few minutes.")
    else:
        cont_b.markdown("") 
        cont_success = st.container()
        # progress_bar = st.progress(0)
        # status_text = st.empty()
        
        with st.spinner("building, please wait ..."):
            cont_log = st.container(height=420)
            s_logger = StreamLogger(cont_log)
            try:
                BRIDGE_BUILD_STATE.is_building = True                
                # status_text.text("Building image...")
                # progress_bar.progress(20)                
                status_ok = BridgeContainerBuilder(s_logger, req).build_bridge_image()
                # progress_bar.progress(100)
            finally:
                BRIDGE_BUILD_STATE.is_building = False
            if status_ok:
                img_name = BridgeImageName.local_image_name(req)
                cont_success.success(f"Image `{img_name}` Built!")
                USAGE_LOG.log_usage(UsageMetric.build_bridge_image)
                if not req.bridge.only_db_drivers: #set the selected image tag this built image.
                    app = AppSettings.load_static()
                    l = img_name + ":latest"
                    if app.selected_image_tag != l:
                        app.selected_image_tag = l
                        app.save()
            else:
                cont_success.error("Image Build Failed")
        st.page_link("src/page/10_Build_Bridge.py", label="Close")

@st.dialog("Edit Build Parameters", width="large")
def edit_build_parameters_dialog(req: BridgeRequest):
    app = AppSettings.load_static()
    base_image_examples = "Base image to use when building the image. This should match the linux distro selected. Examples: " + PageUtil.get_base_image_examples()
    base_image = st.text_input("Base Image (should be based on redhat 9)", req.bridge.base_image, help = f"{base_image_examples}")
    idx_d = 0 if req.bridge.linux_distro not in LINUX_DISTROS else LINUX_DISTROS.index(req.bridge.linux_distro)
    linux_distro = st.selectbox("Linux Distro", LINUX_DISTROS, idx_d, help="Linux distribution to use as the base for building the Bridge container. The selection of database drivers might change based on this selection.")

    driver_names = DriverDefLoader(StreamLogger(st.container())).get_driver_names(linux_distro)
    intersection_drivers = [x for x in req.bridge.include_drivers if x in driver_names]  # remove any invalid items stored in session state.
    if len(intersection_drivers) != len(req.bridge.include_drivers):
        missing_drivers = [driver for driver in req.bridge.include_drivers if driver not in driver_names]
        st.warning(f"Some previously selected database drivers for linux_distro `{linux_distro}` are not available in driver definitions: `{','.join(missing_drivers)}`")
    selected_drivers = st.multiselect("Select Database Drivers", driver_names, default=intersection_drivers)

    col1, col2 = st.columns([5,1])
    if APP_CONFIG.is_internal_build():
        rpm_sources = [BridgeRpmSource.tableau_com, BridgeRpmSource.devbuilds]
        idx = 0 if req.bridge.bridge_rpm_source not in rpm_sources else rpm_sources.index(req.bridge.bridge_rpm_source)
        bridge_rpm_source = col1.selectbox("Bridge RPM Download Source", rpm_sources, index=idx)
    else:
        bridge_rpm_source = BridgeRpmSource.tableau_com
        col1.markdown(f"Bridge RPM Download Source: `{bridge_rpm_source}`")
    req.bridge.bridge_rpm_source = bridge_rpm_source
    rpm_version_devbuilds, rpm_version_tableau, use_minerva_rpm = None, None, None
    bridge_rpm_version_devbuilds_is_specific = None
    username, password = None, None
    if bridge_rpm_source == BridgeRpmSource.devbuilds:
        username = col1.text_input("Devbuilds Username", value=app.devbuilds_username, help="Enter your devbuilds username")
        password = col1.text_input("Devbuilds Password", type="password", value=app.devbuilds_password, help="Enter your devbuilds password")
        col1a, col1b = col1.columns([2,1])
        bridge_rpm_version_devbuilds_is_specific = col1b.checkbox("Specific Version", req.bridge.bridge_rpm_version_devbuilds_is_specific)
        downloader = BridgeRpmDownload(col1, req.bridge.bridge_rpm_source, buildimg_path)
        if bridge_rpm_version_devbuilds_is_specific:
            rpm_version_devbuilds = col1a.text_input("Bridge RPM Version", value=req.bridge.bridge_rpm_version_devbuilds)
            error = downloader.is_valid_version_rpm(rpm_version_devbuilds)
            if error:
                col1a.warning(error)
                st.stop()
            is_downloaded = downloader.is_rpm_filename_already_downloaded(rpm_version_devbuilds)
            col1b.caption(":material/check: downloaded" if is_downloaded else ":material/close: not yet downloaded")
        else:
            if col1b.button("clear RPMs", help="Remove all downloaded Bridge RPMs from the _bridgectl/buildimg_ folder."):
                downloader.clear_rpms()
                st.stop()
            rpm_downloaded = downloader.get_rpm_filename_already_downloaded()
            r = rpm_downloaded if rpm_downloaded else "(latest rpm will be downloaded from devbuild/main)"
            col1a.caption(f"Bridge RPM Version")
            col1a.write(f"`{r}`")
                           # help="This was the tableau-bridge rpm file last downloaded. Click the button 'download newer Bridge RPM' to download a more recent promotion candidate from main branch. Or you can download a specific bridge rpm version from any devbuilds branch and copy it into the `bridgectl/buildimg` folder. The file starting with 'tableau-bridge' and with the most recent modified date will be used.")

        use_minerva_rpm = col1.checkbox("Use Minerva RPM", value=req.bridge.use_minerva_rpm)
    else:
        idx = 0 if req.bridge.bridge_rpm_version_tableau_com not in BridgeRpmTableauCom.LATEST_RPM_VERSIONS else BridgeRpmTableauCom.LATEST_RPM_VERSIONS.index(req.bridge.bridge_rpm_version_tableau_com)
        rpm_version_tableau = col1.selectbox("Bridge RPM from [tableau.com](https://www.tableau.com/support/releases/bridge)", BridgeRpmTableauCom.LATEST_RPM_VERSIONS, index=idx)
    idx_l = 0 if req.bridge.locale not in locale_list else locale_list.index(req.bridge.locale)
    locale = col1.selectbox("Locale", locale_list, idx_l, help="Language pack to use for the container image. A few drivers require this setting. If you are not sure, leave it blank.")
    user_as_tableau = col1.checkbox("container runas user: tableau", value=req.bridge.user_as_tableau, help="when unchecked, the container startup user is set to `root`, otherwise the container user is set to a lower privileged user named `tableau` (more secure)")
    image_name_suffix = col1.text_input("Docker Image Name Suffix (optional)", value=req.bridge.image_name_suffix, help="Optional suffix to append to the image name. You can use this field to help you remember which database drivers were selected or any other information specific to the image.")
    image_name_suffix = image_name_suffix if image_name_suffix is not None else ""
    if not ValidationHelper.is_valid_docker_image_name(image_name_suffix):
        col1.warning(f"Invalid image name suffix. must match pattern {ValidationHelper.valid_docker_image_pattern}")
        st.stop()
    if len(image_name_suffix) >= 50:
        col1.warning(f"Image name suffix must be less than 50 characters. Length is {len(image_name_suffix)}")
        st.stop()
    if user_as_tableau and use_minerva_rpm:
        col1.warning(f"Warning, minerva does not yet support running as non-root user.")

    image_name_suffix = image_name_suffix.lower()

    if col1.button("Save"):
        if bridge_rpm_source == BridgeRpmSource.devbuilds:
            app.devbuilds_username = username
            app.devbuilds_password = password
            app.save()
        save_settings(selected_drivers, bridge_rpm_source, use_minerva_rpm, base_image, user_as_tableau, linux_distro, image_name_suffix, rpm_version_tableau, locale, bridge_rpm_version_devbuilds_is_specific, rpm_version_devbuilds)
        st.rerun()

def validate_paths(unc_network_share_path, host_mount_path, container_mount_path):
    errors = []
    if not unc_network_share_path:
        errors.append("UNC Network Share Path is required.")
    elif not unc_network_share_path.startswith("//"):
        errors.append(r"UNC Network Share Path must start with // (e.g., //server/share).")

    if not host_mount_path:
        errors.append("Host Mount Path is required.")
    elif not os.path.isabs(host_mount_path):
        errors.append("Host Mount Path must be an absolute path.")

    if not container_mount_path:
        errors.append("Container Mount Path is required.")
    elif not container_mount_path.startswith("/"):
        errors.append("Container Mount Path must start with / (e.g., /mnt/share).")
    elif not os.path.isabs(container_mount_path):
        errors.append("Container Mount Path must be an absolute path.")
    return errors

@st.dialog("Edit UNC Path Mappings", width="large")
def edit_unc_path_mappings_dialog(req: BridgeRequest):
    st.info("Define UNC Path Mappings for accessing network shares from the Bridge container. "
            "This allows Tableau Cloud to connect to file-based data sources stored on internal network shares. "
            "Note that the the Network share must be mounted on the host machine before starting the container. ")
    if req.bridge.unc_path_mappings is None:
        req.bridge.unc_path_mappings = {}
    if not req.bridge.unc_path_mappings:
        st.caption(f"No mappings yet defined")
    else:
        st.markdown("### Existing Mappings")
        count = 0
        for unc_path, paths in req.bridge.unc_path_mappings.items():
            paths: dict = paths
            host_mount_path = paths.get(PropNames.host_mount_path)
            container_mount_path = paths.get(PropNames.container_mount_path)
            col1, col2 = st.columns([3, 1])
            col1.markdown(f"- **UNC Network Share Path:** {unc_path}")
            col1.markdown(f"  - **Host Mount Path:** {host_mount_path}")
            col1.markdown(f"  - **Container Mount Path:** {container_mount_path}")
            col1.markdown("---")
            count += 1
            if col2.button("remove mapping", key=f"remove_unc_{count}"):
                del req.bridge.unc_path_mappings[unc_path]
                bridge_settings_file_util.save_settings(req)
                st.success(f"Deleted mapping for UNC Path: {unc_path}")
                sleep(.7)
                st.rerun()
    st.markdown("### Add a mapping")
    unc_network_share_path = st.text_input(
        "UNC Network Share Path",
        key="unc_net",
        help=r"Enter the UNC path to the network share (e.g., \\server\share)."
    )
    host_mount_path = st.text_input(
        "Host Mount Path",
        key="loc_mnt_path",
        help="Specify the path on the local host where the network share has been mounted."
    )
    if host_mount_path:
        if not os.path.exists(host_mount_path):
            st.warning("Host Mount Path does not exist on host")
        else:
            st.success("Host Mount Path exists on host")

    container_mount_path = st.text_input(
        "Container Mount Path",
        key="cont_mnt_path",
        help="Specify the path inside the container where the network share will be accessible."
    )

    if st.button("Add UNC Path Mapping"):
        unc_network_share_path = unc_network_share_path.strip()
        host_mount_path = host_mount_path.strip()
        container_mount_path = container_mount_path.strip()
        errors = validate_paths(unc_network_share_path, host_mount_path, container_mount_path)
        if errors:
            for e in errors:
                st.error(e)
                return
        else:
            req.bridge.unc_path_mappings[unc_network_share_path] = {PropNames.host_mount_path: host_mount_path, PropNames.container_mount_path: container_mount_path}
            bridge_settings_file_util.save_settings(req)
            st.success("UNC Mapping added")
            sleep(.7)
            st.rerun()
    st.info(
        "### Tips:\n"
        "- The mappings are used to mount network shares into the container at startup and tell Bridge how to find them.\n"
        "- UNC mappings are stored in `bridgectl/config/bridge_settings.yml`.\n"
        "- To remove mappings, edit the YAML file directly.\n")
    with st.expander("Tips for Mounting Network Shares on Linux"):
        st.info("- To create a network mapping on Linux, use the `mount` command. For example:\n\n"
        "  ```\n"
        "  sudo mount -t cifs -o credentials=/etc/samba/creds,sec=ntlmssp,vers=3.0 //server/share /mnt/shared_folder\n"
        "  ```\n\n"
        "  Example contents of `/etc/samba/creds`:\n\n"
        "  ```\n"
        "  username=user1\n"
        "  password=pass2\n"
        "  domain=company3.lan\n"
        "  ```"
        )

@st.dialog("Edit Container DNS Mappings and Network Settings", width="large")
def show_edit_dns_mapping_dialog(req: BridgeRequest):
    st.info("Define Local DNS Mappings to add to the /etc/hosts file inside the bridge container. \n"
            "These values will be passed into the --add_hosts parameter when running the bridge container.")
    
    # Add New Mapping Section
    st.markdown("### Add New DNS Mapping")
    with st.container(border=True):
        ch1, ch2 = st.columns([1,1])
        host = ch1.text_input("Hostname", key="host", placeholder="e.g., mydb.test.lan", help="The hostname to map to an IP address")
        ip = ch2.text_input("IP Address", key="ip", placeholder="e.g., 10.22.33.44", help="The IP address for the hostname")
        
        if st.button("Add DNS Mapping", type="primary"):
            host = host.strip()
            ip = ip.strip()
            if not host or not ip:
                st.error("Both Hostname and IP Address are required")
                return
            if not ValidationHelper.is_valid_host(host):
                st.error(f"Invalid Hostname format: {host}")
                return
            if not ValidationHelper.is_valid_ipaddress(ip):
                st.error(f"Invalid IP Address format: {ip}")
                return
            req.bridge.dns_mappings[host] = ip
            bridge_settings_file_util.save_settings(req)
            st.success("DNS Mapping added successfully")
            sleep(.7)
            st.rerun()

    # Existing Mappings Section
    st.markdown("### Current DNS Mappings")
    if req.bridge.dns_mappings is None:
        req.bridge.dns_mappings = {}
    
    if not req.bridge.dns_mappings:
        with st.container(border=True):
            st.caption("No DNS mappings defined yet")
    else:
        with st.container(border=True):
            for host, ip in req.bridge.dns_mappings.items():
                col1, col2, col3 = st.columns([2, 2, 1])
                col1.markdown(f"**Hostname:** `{host}`")
                col2.markdown(f"**IP:** `{ip}`")
                if col3.button("🗑️ Remove", key=f"delete_{host}", type="secondary", use_container_width=True):
                    del req.bridge.dns_mappings[host]
                    bridge_settings_file_util.save_settings(req)
                    st.success(f"Removed mapping for {host}")
                    sleep(.7)
                    st.rerun()              
                # if host != list(req.bridge.dns_mappings.keys())[-1]:
                #     st.divider()
    
    # Network Settings Section
    st.markdown("### Container Network Settings")
    with st.container(border=True):
        idx_n = 0 if req.bridge.docker_network_mode not in VALID_DOCKER_NETWORK_MODES else VALID_DOCKER_NETWORK_MODES.index(req.bridge.docker_network_mode)
        network_mode = st.selectbox(
            "Container Network Mode", 
            VALID_DOCKER_NETWORK_MODES, 
            idx_n,
            help="'bridge' (default) - Use docker's default bridge network.\n'host' - Use the host network stack inside the container."
        )
        
        is_disabled = network_mode == req.bridge.docker_network_mode
        if st.button("Save Network Mode", disabled=is_disabled, type="primary"):
            req.bridge.docker_network_mode = network_mode
            bridge_settings_file_util.save_settings(req)
            st.success("Network mode updated successfully")
            sleep(.7)
            st.rerun()

    with st.expander("ℹ️ DNS Mapping Tips"):
        st.info(
            """
            - DNS mappings allow you to define custom hostname to IP address mappings inside the container
            - These mappings are added to the container's `/etc/hosts` file
            - Useful for connecting to internal services using hostnames
            - Example mapping: `database.internal` → `192.168.1.100`
            """
        )


PageUtil.set_page_config("Build", ":material/build: Build Tableau Bridge Container Image")
page_content()
