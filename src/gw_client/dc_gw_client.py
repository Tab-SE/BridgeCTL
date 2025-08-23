import json
from typing import List

import requests

from src.gw_client.dc_gw_client_models import UpdateCommandDto, RemoteCommand
from src.gw_client.dc_gw_config import DC_GW_BASE_URL


class DcGwClient:
    def __init__(self, gw_token, base_url = None):
        if not base_url:
            self.base_url = DC_GW_BASE_URL
        self.headers = {}
        if gw_token:
            self.headers['api-gw-token'] = gw_token

    def get_version(self):
        url = f"{self.base_url}/api/version"
        response = requests.get(url)
        self.raise_status(url, response)
        version_info = response.json()
        return version_info

    def edge_manager_register(self, payload):
        url = f"{self.base_url}/api/edge/register"
        response = requests.post(url, json=payload, headers=self.headers)
        self.raise_status(url, response)
        return response.json()

    def edge_manager_update(self, payload):
        url = f"{self.base_url}/api/edge/update"
        response = requests.post(url, json=payload, headers=self.headers)
        self.raise_status(url, response)
        return response.json()

    def edge_manager_unregister(self):
        url = f"{self.base_url}/api/edge/unregister"
        response = requests.delete(url, headers=self.headers)
        self.raise_status(url, response)
        return response.json()

    def edge_manager_all_by_site(self):
        url = f"{self.base_url}/api/edge/all_by_site"
        response = requests.get(url, headers=self.headers)
        self.raise_status(url, response)
        return response.json()

    def test_file_upload(self, file_path):
        url = f"{self.base_url}/api/diagnose/log"
        try:
            with open(file_path, 'rb') as file:
                files = {'file': file}
                response = requests.post(url, files=files, headers=self.headers)
                self.raise_status(url, response)
                result = response.json()
                print("File upload successful:")
                print(json.dumps(result, indent=2))
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
        except requests.exceptions.RequestException as e:
            print(f"Error during file upload: {e}")

    def send_new_command(self, payload):
        url = f"{self.base_url}/api/commands/new"
        response = requests.post(url, json=payload, headers=self.headers)
        self.raise_status(url, response)
        return response.json()

    def get_commands(self, just_new: bool = False, as_json: bool = False) -> List[RemoteCommand]:
        f = "new" if just_new else "all"
        url = f"{self.base_url}/api/commands/{f}"
        response = requests.get(url, headers=self.headers)
        self.raise_status(url, response)
        ret = response.json()
        if as_json:
            return response.json()
        commands = []
        for command in ret:
           commands.append(RemoteCommand(**command))
        return commands

    def update_command(self, dto: UpdateCommandDto):
        url = f"{self.base_url}/api/commands/update"
        response = requests.post(url, json=dto.to_dict(), headers=self.headers)
        self.raise_status(url, response)
        return response.json()

    @staticmethod
    def raise_status(url, response):
        if response.status_code not in [200, 201]:
            detail = response.text if hasattr(response, 'text') else None
            raise Exception(f"error calling {url} - {response.status_code} {response.reason} - {detail}")
