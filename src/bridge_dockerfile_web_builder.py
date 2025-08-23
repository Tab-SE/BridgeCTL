import os
from pathlib import Path

from src import download_util
from src.bridge_container_builder import buildimg_path, BridgeContainerBuilder
from src.bridge_rpm_download import BridgeRpmDownload
from src.driver_caddy.driver_script_generator import DriverScriptGenerator
from src.enums import AMD64_PLATFORM
from src.models import LoggerInterface, BridgeRequest, BridgeImageName, BridgeRpmSource


class BridgeDockerfileWebBuilder:
    def __init__(self, logger: LoggerInterface, req: BridgeRequest):
        self.logger: LoggerInterface = logger
        self.req = req
        self.rpm_download = BridgeRpmDownload(logger, req.bridge.bridge_rpm_source, buildimg_path)
        self.script_generator = DriverScriptGenerator(logger, buildimg_path)

    def generate_dockerfile(self):
        if not os.path.exists(buildimg_path):
            os.mkdir(buildimg_path)
        # STEP - start-bridgeclient.sh
        req = self.req
        if not req.bridge.use_minerva():
            sub_run = {"tableau_bridge/bin/run-bridge.sh": "tableau_bridge/bin/TabBridgeClientWorker"}
        else:
            sub_run = None
        docker_file = "Dockerfile"
        start_file = f"{buildimg_path}{os.sep}start-bridgeclient.sh"
        download_util.write_template(
            f"{Path(__file__).parent}/templates/start-bridgeclient.sh",
            start_file,
            True, replace= sub_run)
        with open(start_file, 'r') as file:
            start_contents = file.read()

        # STEP - Locale setup
        locale_setup_script = ""
        if req.bridge.locale:
            locale_setup_script = f"RUN yum install -y glibc-langpack-en\n" \
                        "ENV LANG=en_US.UTF-8 \\\n    LANGUAGE=en_US:en \\\n    LC_ALL=en_US.UTF-8"
            self.logger.info(f"setting locale to: {self.req.bridge.locale}")

        # STEP - Dockerfile
        rpm_file, rpm_url = self.rpm_download.just_get_name_and_url_of_latest(req)
        dockerfile_elements = {
            "#<FROM_BASEIMAGE>": req.bridge.base_image,
            "#<USER_CREATE>": "",
            "#<USER_SET>": "",
            "#<COPY_DRIVER_FILES>": "",
            "#<COPY_BridgeClientConfiguration>": "",
            "#<Locale_Setup>": locale_setup_script,
        }
        BridgeContainerBuilder.set_runas_user(req, dockerfile_elements)

        dest = f"{buildimg_path}/Dockerfile"
        download_util.write_template(
            f"{Path(__file__).parent}/templates/{docker_file}",
            dest,
            replace=dockerfile_elements
        )
        with open(dest, 'r') as file:
            dockerfile_contents = file.read()

        # STEP - build.sh
        build_sh_contents = self.render_build_sh(rpm_file, rpm_url)

        # STEP - download bridge RPM
        if req.bridge.bridge_rpm_source == BridgeRpmSource.devbuilds:
            download_bridge_rpm_contents  = f"#download latest bridge daily promotion-candidate rpm by pasting this url into your browser (you'll be prompted to login to devbuilds web):\n{rpm_url}\n"
        else:
            download_bridge_rpm_contents  = f"#download latest bridge rpm from downloads.tableau.com:\ncurl -O {rpm_url}\n"


        # STEP - drivers
        self.script_generator.gen(req.bridge.include_drivers, req.bridge.linux_distro, False)
        path_download_drivers, path_install_drivers = self.script_generator.script_path_buildimg()
        with open(path_download_drivers, 'r') as file:
            download_drivers_contents = file.read()
        with open(path_install_drivers, 'r') as file:
            install_drivers_contents = file.read()

        # STEP - run_bridge
        run_bridge_contents = self.render_run_bridge()

        # STEP - return scripts
        return dockerfile_contents, start_contents, build_sh_contents, download_bridge_rpm_contents, download_drivers_contents, install_drivers_contents, run_bridge_contents

    def render_build_sh(self, rpm_file, rpm_url):
        cmd = ""
        cmd += f'docker build --tag {BridgeImageName.local_image_name(self.req)} --platform {AMD64_PLATFORM} --no-cache'
        # cmd += f' --build-arg DRIVERS={",".join(self.req.bridge.include_drivers)}'
        cmd += f' --build-arg BRIDGERPM={rpm_file}'
        cmd += f' .'
        return cmd

    def render_run_bridge(self):
        name = BridgeImageName.local_image_name(self.req)
        return f'#!/bin/bash\nBRIDGE_IMAGE_NAME="{name}"\n' + """
TC_SERVER_URL="https://prod-useast-a.online.tableau.com"
SITE_NAME="..."
USER_EMAIL="..."
POOL_ID="..."
TOKEN_NAME="..."
set +o xtrace
TOKEN_VALUE="..."
set -o xtrace
BRIDGE_AGENT_NAME="bridge-${TOKEN_NAME}"

docker run -d --restart=on-failure:1 --name $BRIDGE_AGENT_NAME \\
--platform linux/x86_64 \\
-e AGENT_NAME=$BRIDGE_AGENT_NAME \\
-e TC_SERVER_URL=$TC_SERVER_URL \\
-e SITE_NAME=$SITE_NAME \\
-e USER_EMAIL=$USER_EMAIL \\
-e POOL_ID=$POOL_ID \\
-e TOKEN_NAME=$TOKEN_NAME \\
-e TOKEN_VALUE=$TOKEN_VALUE \\
$BRIDGE_IMAGE_NAME
"""


    def generate_kubectl_run_cmd(self):
        """Generate kubectl run command for deploying a Bridge container"""
        # Get the image name from the build settings
        image_name = BridgeImageName.local_image_name(self.req)
        # image_name = f"tableau-bridge-{req.bridge.linux_distro.lower()}"
        
        # Create the kubectl run command
        kubectl_cmd = """#!/bin/bash
# Set your Bridge configuration variables
BRIDGE_IMAGE_NAME="tableau-bridge-""" + self.req.bridge.linux_distro.lower() + """:latest"
TC_SERVER_URL="https://prod-useast-a.online.tableau.com"  # Update with your pod URL
SITE_NAME="your_site_name"
USER_EMAIL="your_email@example.com"
POOL_ID="your_pool_id"
TOKEN_NAME="your_token_name"
set +o xtrace
TOKEN_VALUE="your_token_secret"
set -o xtrace
BRIDGE_AGENT_NAME="bridge-${TOKEN_NAME}"

# Run the pod using kubectl run
kubectl run ${BRIDGE_AGENT_NAME} \\
--image=${BRIDGE_IMAGE_NAME} \\
--image-pull-policy=Never \\  # Use 'Always' for remote registries
--env="AGENT_NAME=${BRIDGE_AGENT_NAME}" \\
--env="TC_SERVER_URL=${TC_SERVER_URL}" \\
--env="SITE_NAME=${SITE_NAME}" \\
--env="USER_EMAIL=${USER_EMAIL}" \\
--env="POOL_ID=${POOL_ID}" \\
--env="TOKEN_NAME=${TOKEN_NAME}" \\
--env="TOKEN_VALUE=${TOKEN_VALUE}" \\
--labels="app=tableau-bridge,tableau.com/sitename=${SITE_NAME},tableau.com/pool-id=${POOL_ID}" \\
--requests="cpu=500m,memory=1Gi" \\
--limits="cpu=1000m,memory=2Gi"

# Check the pod status
echo "Checking pod status..."
kubectl get pods | grep ${BRIDGE_AGENT_NAME}
"""
        
        return kubectl_cmd
