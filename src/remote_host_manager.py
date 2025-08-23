from src import models
from src.models import LoggerInterface, AppSettings


class RemoteHostManager:
    def __init__(self, logger: LoggerInterface, req: models.BridgeRequest, token: models.PatToken):
        self.logger: LoggerInterface = logger
        self.req: models.BridgeRequest = req
        self.token: models.PatToken = token

    def run_bridge_container_on_remote_host(self, remote_host: str, remote_username, just_script: bool = False):
        # ref:   https://chatgpt.com/c/675f9d56-9998-8013-8985-956662f86ecf

        # STEP - docker export image to .tar and zip it
        img_tar_name = "image.tar"
        cmd = f"docker save <image-name> -o {img_tar_name}"
        cmd = f"gzip {img_tar_name}"  # gzip image.tar

        # STEP - scp zipped image to remote machine
        img_zip_name = "image.tar.gz"
        cmd = f"scp {img_zip_name} {remote_username}@{remote_host}:~/"  # scp image.tar.gz user@remote-host:/path/to/destination/

        # STEP - On the remote machine: unzip and load image to docker
        cmd = f"gunzip ~/{img_zip_name}"

        #   gunzip /path/to/destination/image.tar.gz
        cmd = f"docker load < ~/{img_zip_name}"

        #   docker load < /path/to/destination/image.tar

        # STEP - On the remote machine: run the container
        #  docker run -d --restart=on-failure:1 \


