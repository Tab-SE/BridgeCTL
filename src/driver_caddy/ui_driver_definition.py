import streamlit as st

from src.page.ui_lib.stream_logger import StreamLogger
from src import bridge_container_builder, bridge_settings_file_util
from src.cli.app_config import APP_CONFIG
from src.driver_caddy.driver_script_generator import DriverDefLoader
from src.lib.general_helper import StringUtils


class UiDriverDefinition:
    @st.dialog("Import Driver Definition File", width="large")
    @staticmethod
    def define_drivers(req):
        if APP_CONFIG.is_internal_build():
            from src.internal.devbuilds.devbuilds_config import DevBuildsConfig
            help_link = DevBuildsConfig.driver_caddy_help_link()
        else:
            help_link = "https://github.com/tableau/bridgectl/blob/main/driver_caddy.md"
        st.info(f"Instructions: Please create and upload a driver install definition YAML file. Please see the [documentation]({help_link}).")
        p = DriverDefLoader.get_active_path()
        if not p or not p.exists():
            p = "(not yet defined)"
            st.markdown(f"current driver definition file: `{p}`")
        else:
            ps = StringUtils.remove_before(str(p), "bridgectl/")
            st.markdown(f"current driver definition file: `{ps}`")
            driver_names = DriverDefLoader(StreamLogger(st.container())).get_driver_names(req.bridge.linux_distro)
            col1,col2 = st.columns([1,2])
            col2.markdown(f"for `{req.bridge.linux_distro}` there are `{len(driver_names)}` drivers defined")
        st.markdown("")
        st.markdown("")
        driver_def_path = st.file_uploader("Upload Driver definition file", type=["yaml"], accept_multiple_files=False)
        if driver_def_path:
            with open(DriverDefLoader.user_drivers_def_path, "wb") as f:
                f.write(driver_def_path.read())
            st.success(f"Successfully stored at: {DriverDefLoader.user_drivers_def_path}")
            errors = DriverDefLoader(StreamLogger(st.container())).validate_def_file()
            if errors:
                st.error(f"Errors found in driver definition file: {errors}")
            else:
                st.success("Driver definition file is valid.")
        st.markdown("---")
        st.page_link("src/page/10_Build_Bridge.py", label="Close")


    @staticmethod
    @st.dialog("Upload Driver Setup Files", width="large")
    def upload_driver_setup_files():
        path_short = StringUtils.remove_before(str(bridge_container_builder.buildimg_drivers_path), "bridgectl/")
        cont = st.container(border=True)
        cont.markdown(f"Upload database driver install files referenced in the driver definition yaml file (drivers.yaml).\n"
                      f"- The upload file will be stored here: `{path_short}`\n"
                      f"- and can be referenced in drivers.yaml like this: `download_url: LOCAL my_driver_v1.jar`\n")
                      # f"- Please see the [documentation](https://github.com/tableau/bridgectl/blob/main/driver_caddy.md)\n")
        driver_file = st.file_uploader("Driver Install File",
                                     accept_multiple_files=False,
                                     help="Select a driver installation file to upload")
        if driver_file:
            if not bridge_container_builder.buildimg_drivers_path.exists():
                bridge_container_builder.buildimg_drivers_path.mkdir(parents=True)
            driver_path = bridge_container_builder.buildimg_drivers_path / driver_file.name
            with open(driver_path, "wb") as f:
                f.write(driver_file.read())
            st.success(f"Successfully saved to: {driver_path}")
