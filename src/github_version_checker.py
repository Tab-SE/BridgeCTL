import requests
from requests.adapters import HTTPAdapter, Retry

from src.cli.app_config import APP_CONFIG


class GithubVersionChecker:
    SETUP_RELEASE = "setup"

    @staticmethod
    def get_releases_home() -> str:
        if APP_CONFIG.is_internal_build():
            return f"http://{APP_CONFIG.target_github_repo}"
        else:
            return f"https://github.com/{APP_CONFIG.target_github_repo}/releases"


    def get_latest_app_version(self) -> str:
        if APP_CONFIG.is_internal_build():
            # from src.devbuilds.github_util_devbuilds import GithubUtilDevbuilds
            # response_text = GithubUtilDevbuilds().get_latest_version()
            app_version_url = f"{self.get_releases_home()}/app_version.yml"
            response = requests.get(app_version_url, timeout=5)
            response.raise_for_status()
            response_text = response.text
        else:
            app_version_url = f"{self.get_releases_home()}/download/{self.SETUP_RELEASE}/app_version.yml"
            response = requests.get(app_version_url)
            response.raise_for_status()
            response_text = response.text
        parts = response_text.split(":")
        if parts[0] != "app_version":
            raise Exception(f"Error: Unexpected format from {app_version_url}\nresponse: {response.text}")
        return parts[1].strip()

    def get_setup_url(self) -> str:
        return f"{self.get_releases_home()}/download/{self.SETUP_RELEASE}/bridgectl_setup.py"

    @staticmethod
    def download_file(file_url, local_filename):
        if APP_CONFIG.is_internal_build():
            setup_url = f"http://{APP_CONFIG.target_github_repo}/bridgectl_setup.py"
            # print(f"downloading {url}")
            response = requests.get(setup_url)
            if response.status_code == 200:
                with open(local_filename, 'wb') as file:
                    file.write(response.content)
            else:
                raise Exception(f"Failed to download from {setup_url}. status_code: {response.status_code}")
            # from src.devbuilds.github_util_devbuilds import GithubUtilDevbuilds
            # GithubUtilDevbuilds().download_bridgectl_setup(local_filename)
            return
        # Based on: https://stackoverflow.com/a/35504626
        s = requests.Session()
        retries = Retry(total=5, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
        s.mount('https://', HTTPAdapter(max_retries=retries))

        response = s.get(file_url, stream=True)
        if response.status_code != 200:
            raise Exception(f"Error: Unable to download file. Status code {response.status_code}")

        with open(local_filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
