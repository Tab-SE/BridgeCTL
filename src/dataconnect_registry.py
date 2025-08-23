from typing import List

import requests

from src.models import LoggerInterface
from src.subprocess_util import SubProcess
from dataclasses import dataclass

@dataclass
class CrImage:
    repo_name: str
    tags: List[str]

@dataclass
class DCRegistry:
    hostname: str = "container-registry.distributed-cloud.salesforce.com"
    username: str = "admin"
    password: str = ""

class DataConnectRegistryLogic:
    def __init__(self, logger: LoggerInterface, dc_reg: DCRegistry):
        self.logger = logger
        self.dc_reg = dc_reg

    def get_remote_base_image_tag(self, pool_id: str):
        return f"{self.dc_reg.hostname}/bridge-base:{pool_id}"

    def get_push_script(self, local_image_tag, pool_id: str):
        image_push_url = self.get_remote_base_image_tag(pool_id)
        cmds = [
            f'echo {self.dc_reg.password} | docker login --username {self.dc_reg.username} --password-stdin {self.dc_reg.hostname}',
            f'docker tag {local_image_tag} {image_push_url}',
            f'docker push {image_push_url}']
        return cmds

    def login(self, show_only: bool = False) -> (bool, str):
        login_cmd = f"echo {self.dc_reg.password} | docker login --username {self.dc_reg.username} --password-stdin {self.dc_reg.hostname}"
        # if show_only:
        #     self.logger.info(login_cmd)
        #     return True, None
        # else:
        login_cmd_d = login_cmd.replace(self.dc_reg.password, "*****")
        self.logger.info(login_cmd_d)
        stdout, stderr, return_code = SubProcess.run_cmd_light(login_cmd)
        self.logger.info(f"stdout: {stdout}")
        return return_code == 0, stderr

    def get_repos_with_tags(self) -> List[CrImage]:
        url = f"https://{self.dc_reg.hostname}/v2/_catalog"
        ret = requests.get(url, auth=(self.dc_reg.username, self.dc_reg.password), verify=False)
        images = []
        if ret.status_code == 200:
            repos_ret = ret.json().get("repositories", [])
            for name in repos_ret:
                cr = CrImage(repo_name=name, tags=[])
                images.append(cr)
                url_tags = f"https://{self.dc_reg.hostname}/v2/{name}/tags/list"
                ret_tags = requests.get(url_tags, auth=(self.dc_reg.username, self.dc_reg.password), verify=False)
                if ret_tags.status_code == 200:
                    tags = ret_tags.json().get("tags", [])
                    cr.tags = tags
                else:
                    self.logger.error(f"Error: {ret_tags.status_code} calling {url_tags}")
        else:
            self.logger.error(f"Error: {ret.status_code} {ret.reason} calling {url}")

        return images



