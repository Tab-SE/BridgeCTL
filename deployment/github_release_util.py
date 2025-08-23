import os
from typing import List

from github import Github
from github.GitRelease import GitRelease

from src.github_version_checker import GithubVersionChecker
from src.models import LoggerInterface


class GithubReleaseUtil:
    def __init__(self, logger: LoggerInterface, target_env, repo_path):
        self.logger = logger
        k = f'dc_github_token_{target_env}'
        gh_token = os.getenv(k)
        if not gh_token:
            raise Exception(f"env var not set '{k}'")
        self.repo_client = Github(gh_token).get_repo(repo_path)

    def push_release(self, release_tag, asset_paths: List[str] = None, prerelease = False):
        self.logger.info(f"pushing github release '{release_tag}'")
        release = self.repo_client.create_git_release(
            tag= release_tag,
            name= f"{release_tag}",
            message= f"{release_tag}",
            prerelease=prerelease
        )
        if asset_paths:
            for asset in asset_paths:
                self.logger.info(f"   uploading asset {asset}")
                release.upload_asset(asset)

    def get_release_by_tag(self, tag_name):
        try:
            release = self.repo_client.get_release(tag_name)
        except Exception as e:
            if hasattr(e, 'data') and e.data.get('message') == "Not Found":
                return None
            raise
        return release

    def create_latest_metadata_release(self, setup_file: str, app_version_file: str):
        try:
            release = self.get_release_by_tag(GithubVersionChecker.SETUP_RELEASE)
            if release:
                release.delete_release()
            self.push_release(GithubVersionChecker.SETUP_RELEASE, asset_paths= [setup_file, app_version_file], prerelease=True)
        except Exception as e:
            if hasattr(e, 'data') and e.data.get('message') == "Not Found":
                return None
            raise

    def get_latest_release(self) -> GitRelease:
        return self.repo_client.get_latest_release()

    def list_releases(self):
        releases = self.repo_client.get_releases()
        names = []
        for release in releases:
            names.append(release.tag_name)
        return names

    def delete_release(self, release):
        release.delete_release()




