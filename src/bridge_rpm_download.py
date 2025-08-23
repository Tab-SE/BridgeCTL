import os

from src import models, bridge_settings_file_util
from src.bridge_rpm_tableau_com import BridgeRpmTableauCom
from src.lib.general_helper import StringUtils
from src.models import LoggerInterface, BridgeRequest


class BridgeRpmDownload:
    def __init__(self, logger: LoggerInterface, bridge_rpm_source: str, buildimg_path: str):
        self.logger = logger
        self.bridge_rpm_source = bridge_rpm_source
        self.buildimg_path = buildimg_path

    def just_get_name_and_url_of_latest(self, req: BridgeRequest) -> (str, str):
        if self.bridge_rpm_source == models.BridgeRpmSource.devbuilds:
            from src.internal.devbuilds.bridge_rpm_download_devbuilds import BridgeRpmDownloadDevbuilds
            rpm_filename, url = BridgeRpmDownloadDevbuilds(self.logger, self.buildimg_path).just_get_name_and_url_of_main_latest()
            return rpm_filename, url
        else:
            rpm_file_name = BridgeRpmTableauCom.get_filename_from_version(req.bridge.bridge_rpm_version_tableau_com)
            url = BridgeRpmTableauCom.get_url_from_version(req.bridge.bridge_rpm_version_tableau_com)
            return rpm_file_name, url

    def get_rpm_filename_already_downloaded(self) -> str:
        """
        Get the filename of the latest downloaded rpm file.
        """
        if self.bridge_rpm_source == models.BridgeRpmSource.devbuilds:
            prefix = "tableau-bridge"
        else:
            prefix = "TableauBridge"
        if os.path.exists(self.buildimg_path):
            files = [f for f in os.listdir(self.buildimg_path) if f.startswith(prefix) and f.endswith(".rpm")]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.buildimg_path, x)), reverse=True) #sort by newest file first
            if files:
                return files[0]
            else:
                return None
        return ""

    def is_rpm_filename_already_downloaded(self, rpm_version) -> bool:
        if not rpm_version or not os.path.exists(self.buildimg_path):
            return False
        expected_filename = self.get_filename_from_version(rpm_version)
        return os.path.exists(os.path.join(self.buildimg_path, expected_filename))

    def route_download_request_for_bridge_rpm(self, req: BridgeRequest) -> str:
        if self.bridge_rpm_source == models.BridgeRpmSource.devbuilds:
            from src.internal.devbuilds.bridge_rpm_download_devbuilds import BridgeRpmDownloadDevbuilds
            devbuilds_downloader = BridgeRpmDownloadDevbuilds(self.logger, self.buildimg_path)
            if req.bridge.bridge_rpm_version_devbuilds_is_specific:
                if self.is_rpm_filename_already_downloaded(req.bridge.bridge_rpm_version_devbuilds):
                    rpm_file = self.get_filename_from_version(req.bridge.bridge_rpm_version_devbuilds) #f"tableau-bridge-{req.bridge.bridge_rpm_version_devbuilds}.x86_64.rpm"
                else:
                    rpm_file = devbuilds_downloader.download_specific_rpm_version(req.bridge.bridge_rpm_version_devbuilds)
            else:
                rpm_downloaded = self.get_rpm_filename_already_downloaded()
                if rpm_downloaded:
                    rpm_file = rpm_downloaded
                else:
                    rpm_file = devbuilds_downloader.determine_and_download_latest_rpm_from_devbuilds()
                ver = BridgeRpmDownloadDevbuilds.get_version_from_filename(rpm_file)
                if req.bridge.bridge_rpm_version_devbuilds != ver:
                    req.bridge.bridge_rpm_version_devbuilds = ver
                    bridge_settings_file_util.save_settings(req)
        elif self.bridge_rpm_source == models.BridgeRpmSource.tableau_com:
            if req.bridge.bridge_rpm_version_tableau_com not in BridgeRpmTableauCom.LATEST_RPM_VERSIONS:
                req.bridge.bridge_rpm_version_tableau_com = BridgeRpmTableauCom.LATEST_RPM_VERSIONS[0]
                self.logger.info(f"updating bridge rpm to latest valid version: {req.bridge.bridge_rpm_version_tableau_com}")
                bridge_settings_file_util.save_settings(req)
            rpm_file = BridgeRpmTableauCom.determine_and_download_latest_rpm_from_tableau_com(self.logger, req, self.buildimg_path)
        else:
            raise Exception(f"bridge_rpm_source {self.bridge_rpm_source} not supported. valid values: {StringUtils.get_values_from_class(models.BridgeRpmSource)}'")
        return rpm_file

    def get_version_from_filename(self, rpm_filename: str) -> str:
        if self.bridge_rpm_source == models.BridgeRpmSource.devbuilds:
            return rpm_filename.replace('tableau-bridge-', '').replace('.x86_64.rpm', '')
        else:
            return rpm_filename.replace('TableauBridge-', '').replace('.x86_64.rpm', '')

    def get_filename_from_version(self, rpm_version: str) -> str:
        if not rpm_version:
            return None
        if self.bridge_rpm_source == models.BridgeRpmSource.devbuilds:
            return f"tableau-bridge-{rpm_version}.x86_64.rpm"
        else:
            return f"TableauBridge-{rpm_version}.x86_64.rpm"

    def clear_rpms(self) -> None:
        """
        Remove all Bridge RPM files from the buildimg directory.
        """
        if not os.path.exists(self.buildimg_path):
            return

        # Find and remove all matching RPM files
        count = 0
        for file in os.listdir(self.buildimg_path):
            if (file.startswith("tableau-bridge") or file.startswith("TableauBridge")) and file.endswith(".rpm"):
                file_path = os.path.join(self.buildimg_path, file)
                try:
                    os.remove(file_path)
                    self.logger.info(f"Removed RPM file: {file}")
                    count += 1
                except OSError as e:
                    self.logger.warning(f"Failed to remove {file}: {str(e)}")
        if count == 0:
            self.logger.info("No RPM files found to remove")
    
    def is_valid_version_rpm(self, rpm_version: str) -> str:
        if self.bridge_rpm_source == models.BridgeRpmSource.devbuilds:
            from src.internal.devbuilds.bridge_rpm_download_devbuilds import BridgeRpmDownloadDevbuilds
            return BridgeRpmDownloadDevbuilds.is_valid_version_rpm(rpm_version)
        else:
            return None
