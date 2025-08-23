import os
import random
import shutil
import string
import traceback
import zipfile
from fnmatch import fnmatch
from pathlib import Path
from typing import List
from zipfile import ZipFile

import yaml
from packaging import version

from deployment.deploy_metrics import DeployMetrics
from deployment.github_release_util import GithubReleaseUtil
from deployment.metrics.plot_metrics import PlotGithubMetrics
from deployment.scp_util import ScpUtil
from src.cli.app_config import APP_CONFIG, DeployEnviron
from src.driver_caddy.driver_script_generator import DriverScriptGenerator
from src.github_version_checker import GithubVersionChecker
from src.models import LoggerInterface


class PipelineLogger(LoggerInterface):
    def info(self, msg = ""):
        print(msg)

    def warning(self,  msg: str):
        print("WARNING: " + msg)

    def error(self, msg, ex: Exception = None):
        traceback.print_exc()
        print("ERROR: " + msg)


class BuildDeploymentPkg:
    FILES_IGNORE_LIST = ['*.pyc', '__pycache__', '*.log', '.git', '.idea', '.vscode', '.github', '*venv*', '.DS_Store', '.env']
    logger = PipelineLogger()

    def __init__(self, target_env):
        self.target_env = target_env
        # self.validate_env()
        self.target_env_config = Path(__file__).parent / "environs" / f"{self.target_env}.yml"

        with open(self.target_env_config) as f:
            t = yaml.safe_load(f)
            self.target_github_repo = t["target_github_repo"]
            self.pem_path = t.get("pem_path")

    def is_internal_builds_version(self):
        return self.target_env == DeployEnviron.internal

    @staticmethod
    def validate_env(target_env):
        if not any(target_env == env for env in vars(DeployEnviron)):
            print(f"invalid TARGET_ENV: {target_env}")
            return False
        return True

    def ignore_names(self, src_dir, names):
        """ ignore files in FILES_IGNORE_LIST, called by shutil.copytree """
        out = []
        for n in names:
            for ign in self.FILES_IGNORE_LIST:
                if fnmatch(n, ign):
                    out.append(n)
        return out

    def zip_files(self, zip_name: str, file_names_to_zip: List[Path]):
        with ZipFile(zip_name, 'w') as zipf:
            for file in file_names_to_zip:
                zipf.write(file, arcname=file.name)

    def zip_folder(self, zip_name, target_dir):
        zip_obj = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        root_len = len(str(target_dir)) + 1
        for base, dirs, files in os.walk(target_dir):
            for file in files:
                fn = os.path.join(base, file)
                zip_obj.write(fn, fn[root_len:])

    def get_random_string(self, length):
        letters = string.ascii_lowercase
        result_str = ''.join(random.choice(letters) for i in range(length))
        return result_str

    def count_files_in_directory(self, dir_path):
        return len([path for path, dirs, files in os.walk(dir_path) for file in files])

    @staticmethod
    def replace_text(template_file: str or Path, out_file: str or Path, replace: dict):
        if template_file:
            shutil.copy(template_file, out_file)
        with open(out_file, 'r+') as f:
            content = f.read()
            for k, v in replace.items():
                content = content.replace(k, str(v))
            f.seek(0)
            f.write(content)
            f.truncate()

    @staticmethod
    def replace_line_with_prefix(template_file: str or Path, out_file: str or Path, replace: dict):
        """
        Copies the content of 'template_file' to 'out_file', then modifies 'out_file' by
        replacing entire lines based on the 'replace' dictionary. Each line in 'out_file'
        that starts with a key from 'replace' is replaced by the key concatenated with its
        corresponding value.
        """
        if template_file:
            shutil.copy(template_file, out_file)
        with open(out_file, 'r') as f:
            lines = f.readlines()
        with open(out_file, 'w') as f:
            for line in lines:
                for k, v in replace.items():
                    if line.startswith(k):
                        line = k + str(v) + '\n'
                        break
                f.write(line)

    def deploy(self):
        self.logger.info("================================")
        self.logger.info(f"building bridgectl setup package")
        self.logger.info("================================")

        current_version = version.parse(APP_CONFIG.app_version)
        new_version = f'{current_version.major}.{current_version.minor}.{current_version.micro + 1}'

        self.logger.info(f"new_version: {new_version}")
        self.logger.info(f"target_github_repo: {self.target_github_repo}")

        APP_CONFIG.app_version = new_version
        APP_CONFIG.save()

        self.logger.info("\nSTEP - copy files to /tmp/bridgectl/new_version")
        tmp_bridgectl = Path(f"/tmp/bridgectl")
        tmp_bridgectl.mkdir(exist_ok=True)
        tmp_dir = tmp_bridgectl / new_version
        tmp_dir.mkdir()
        deploy_dir = Path(__file__).parent
        shutil.copytree(deploy_dir.parent / "src", tmp_dir / "src", ignore=self.ignore_names)
        self.logger.info("\n  SUB-STEP - remove internal-only files")
        if not self.is_internal_builds_version() and False: #disable for now
            shutil.rmtree(tmp_dir / "src" / "internal")

        # shutil.copytree(deploy_dir.parent / "example_scripts", tmp_dir / "example_scripts", ignore=self.ignore_names)
        shutil.copytree(deploy_dir.parent / ".streamlit", tmp_dir / ".streamlit", ignore=self.ignore_names)
        single_files = [deploy_dir.parent/"start.py", deploy_dir.parent/"requirements.txt", deploy_dir.parent/"Home.py"]
        for file_name in single_files:
            shutil.copyfile(file_name, tmp_dir / file_name.name)

        setup_file = tmp_dir / "deployment" / "bridgectl_setup.py"
        app_config_file = tmp_dir / "src" / "cli" / "app_config.yaml"
        self.logger.info(f"writing target_github_url to {setup_file} and {app_config_file}")
        setup_file.parent.mkdir(exist_ok=True)
        self.replace_text(deploy_dir/"bridgectl_setup.py", setup_file,  {"<target_github_repo>": self.target_github_repo, "<latest_version>": new_version})
        shutil.copyfile(setup_file, setup_file.parent.parent.parent / setup_file.name)
        self.replace_line_with_prefix(None, app_config_file,  {"target_github_repo: ": self.target_github_repo})
        self.replace_line_with_prefix(None, app_config_file,  {"deployment_environment: ": self.target_env})
        app_version_file = tmp_dir / "deployment" / "app_version.yml" # file pushed to 'setup' release on github declaring the latest available version
        self.replace_text(deploy_dir/"app_version.yml", app_version_file,  {"<app_version>": new_version})
        streamlit_config_toml = tmp_dir / ".streamlit" / "config.toml"
        streamlit_config_toml_template = streamlit_config_toml.parent / "config_template.toml"
        shutil.move(streamlit_config_toml, streamlit_config_toml_template)
        self.replace_line_with_prefix(None, streamlit_config_toml_template,  {"runOnSave = ": "false"})
        if not self.is_internal_builds_version():
            enforce_local_for_download_urls = False
            if enforce_local_for_download_urls:
                self.logger.info("changing driver download command to local")
                driver_yml = tmp_dir / "src" / "driver_caddy" / "drivers.yaml"
                DriverScriptGenerator.change_download_urls_to_local(driver_yml)
            else:
                self.logger.info("skipping changing driver download command to LOCAL")
            self.replace_text(None, tmp_dir / "requirements.txt", {"requests-ntlm>=1.3.0": ""})

        # STEP - zip
        zip_filename = f"bridgectl_v{new_version}.zip"
        bridgectl_zip_filename = str(tmp_bridgectl / zip_filename)
        count_files = self.count_files_in_directory(tmp_dir)
        self.logger.info(f"creating zip: {bridgectl_zip_filename} which contains {count_files} files")
        self.zip_folder(bridgectl_zip_filename, tmp_dir)
        download_zip_filename = str(tmp_bridgectl / f"bridgectl_download.zip")
        b_setup = tmp_bridgectl / "bridgectl_setup.py"
        files = [b_setup, tmp_bridgectl / bridgectl_zip_filename] #, Path(__file__).parent / "README.md"]
        self.zip_files(download_zip_filename, files)

        self.logger.info("\nSTEP - Publishing")
        if self.is_internal_builds_version():
            scp = ScpUtil(self.logger, self.target_github_repo, self.pem_path, self.target_github_repo)
            scp.push_file(bridgectl_zip_filename)
            scp.push_file(b_setup)
            scp.push_file(app_version_file)
        else:
            gh = GithubReleaseUtil(self.logger, self.target_env, self.target_github_repo)
            gh.push_release(new_version, asset_paths=[bridgectl_zip_filename, download_zip_filename])
            gh.create_latest_metadata_release(str(setup_file), str(app_version_file))

        self.logger.info("================================")
        self.logger.info(f"success pushing {new_version} to {self.target_github_repo}")
        self.logger.info("================================")

    def get_metrics(self):
        self.logger.info("================================")
        self.logger.info(f"get bridgectl metrics")
        self.logger.info("================================")
        gh = GithubReleaseUtil(self.logger, self.target_env, self.target_github_repo)
        dm = DeployMetrics(self.target_env, gh)
        dm.get_metrics()

    def delete_old_releases(self):
        self.logger.info("================================")
        self.logger.info(f"delete old releases")
        self.logger.info("================================")

        gh = GithubReleaseUtil(self.logger, self.target_env, self.target_github_repo)
        names = gh.list_releases()
        count = 0
        print("total releases: ", len(names))
        print("releases: ", names)
        how_many_to_keep = 5
        print("how_many_to_keep: ", how_many_to_keep)
        print("how_many_to_delete: ", len(names) - how_many_to_keep)

        confirm = input(f"Are you sure you want to delete oldest releases? (y/n): ")
        if confirm.strip().lower() not in ["y", "yes"]:
            print("exiting")
            return
        if len(names) < how_many_to_keep:
            print(f"not enough releases to delete, only {len(names)}")
            return
        for name in names:
            print(f"count:{count}, name:{name}")
            if name == GithubVersionChecker.SETUP_RELEASE:
                print(f"skipping setup release: {name}")
                continue
            count += 1
            if count < how_many_to_keep: #skip the newest releases
                print("  keeping")
                continue
            print(f"\nDELETING old release: {name}")
            release = gh.get_release_by_tag(name)
            gh.delete_release(release)


if __name__ == '__main__':
    target_env = input(f"which environment? (dev, beta, stable, internal): ")
    target_env = target_env.lower().strip()
    if not BuildDeploymentPkg.validate_env(target_env):
        exit(1)
    bp = BuildDeploymentPkg(target_env)
    action = input(f"which action? (deploy, metrics, delete, plot): ")
    action = action.lower().strip()
    if action == "metrics":
        bp.get_metrics()
    elif action == "delete":
        bp.delete_old_releases()
    elif action == "deploy":
        bp.deploy()
    elif action == "plot":
        PlotGithubMetrics.plot(target_env)
    else:
        print(f"invalid action: {action}")
        exit(1)
