import os
from src import download_util
from src.models import BridgeRequest


class BridgeRpmTableauCom:
    LATEST_RPM_VERSIONS = ["20243.25.0114.1153", "20243.24.1211.0901", "20243.24.1112.0850", "20243.24.1010.1014", "20242.24.1011.1414", "20242.24.0910.0334"]

    @classmethod
    def get_url_from_version(cls, version):
        if version is None:
            version = ""
        return f"https://downloads.tableau.com/tssoftware/TableauBridge-{version}.x86_64.rpm"

    @staticmethod
    def get_filename_from_version(version):
        if version is None:
            version = ""
        return f"TableauBridge-{version}.x86_64.rpm"

    @staticmethod
    def determine_and_download_latest_rpm_from_tableau_com(logger, req: BridgeRequest, buildimg_path):
        rpm_file_name = BridgeRpmTableauCom.get_filename_from_version(req.bridge.bridge_rpm_version_tableau_com)

        asset_full_name = f"{buildimg_path}/{rpm_file_name}"
        if os.path.exists(asset_full_name):
            logger.info(f"Latest Bridge RPM already downloaded: {asset_full_name}")
            return rpm_file_name
        rpm_url = BridgeRpmTableauCom.get_url_from_version(req.bridge.bridge_rpm_version_tableau_com)
        logger.info(f"Downloading Bridge RPM: {rpm_url}")
        download_util.download_file(rpm_url, asset_full_name)
        return rpm_file_name