import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from typing import List

from src.page.ui_lib.stream_logger import StreamLogger
from src.models import BridgeRpmSource


class LogSourceType:
    docker = "docker"
    disk = "disk"
    k8s = "k8s"

    @classmethod
    def get_source_icon(cls, source_type: str) -> str:
        source_icons = {
            cls.docker: "🐳",
            cls.disk: "📁",
            cls.k8s: "⎈"
        }
        return source_icons.get(source_type, "")

    @classmethod
    def get_source_title(cls, source_type: str) -> str:
        source_titles = {
            cls.docker: "Docker",
            cls.disk: "Disk",
            cls.k8s: "Kubernetes"
        }
        return source_titles.get(source_type, "")


@dataclass
class BridgeLogFile:
    def __init__(self, full_path: str):
        self.name = os.path.basename(full_path)
        self.full_path = full_path
        self.mod_time = os.path.getmtime(full_path)
        prefix = self.name.split("_")[0]
        if prefix == "TabBridgeCliJob":
            prefix = self.name.split("_")[0] + "_" + self.name.split("_")[1]
        self.prefix = prefix
        self.size = os.path.getsize(full_path)
        self.content_type = self.set_content_type(self.name)

    name: str
    full_path: str
    mod_time: float
    prefix: str
    size: int
    content_type: str = None # ContentTypes

    def set_content_type(self, filename: str):
        if filename.startswith("jprotocolserver"):
            return ContentType.txt
        if filename.endswith(".log"):
            return ContentType.json
        if filename.endswith(".json"):
            return ContentType.json
        if filename.startswith("stdout"):
            return ContentType.txt
        if filename.startswith("tabprotosrv"):
            return ContentType.json
        return ContentType.unknown

    def format_size(self):
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.2f} KB"
        else:
            return f"{self.size / (1024 * 1024):.2f} MB"  # Megabytes

    def format(self):
        return f"{self.name:40},   {self.format_size():10}  ({self.content_type})"


class ContentType:
    txt = "txt"
    json = "json"
    unknown = "unknown"


class BridgeLogs:
    number_log_files_to_keep = 10

    @staticmethod
    def list_log_files(path: str, include_pattern: str = None) -> List[BridgeLogFile]:
        """
        Lists files in the given directory path, optionally filtering them by a regex pattern,
        sorted by last modification date.

        :param path: The directory path to list files from.
        :param include_pattern: Optional regex pattern to filter files. Only files matching the pattern will be included.
        :return: A list of file names sorted by modification date.
        """
        pattern = re.compile(include_pattern) if include_pattern else None
        log_files = []
        for item_name in os.listdir(path):
            full_path = os.path.join(path, item_name)
            if os.path.isfile(full_path) and not item_name.startswith("."):
                if not pattern or pattern.search(item_name):
                    lf = BridgeLogFile(full_path)
                    log_files.append(lf)
        log_files.sort(key=lambda x: x.name.lower())
        return log_files

    @staticmethod
    def get_latest_per_group(files: List[BridgeLogFile]):
        groups = BridgeLogs.group_files_by_prefix(files, True)
        result = []
        for g, items in groups.items():
            result.append(items[0])
        return result

    @staticmethod
    def group_files_by_prefix(files: List[BridgeLogFile], sort_by_mod_date: bool = False):
        groups = defaultdict(list)
        for file in files:
            groups[file.prefix].append(file)
        if sort_by_mod_date:
            for g, items in groups.items():
                items.sort(key=lambda x: x.mod_time, reverse=True)
        return groups

    @staticmethod
    def archive_log_files(logger: StreamLogger, log_folder: str, groups: dict):
        archive_subdir = "archive_logs"
        archive_path = os.path.join(log_folder, archive_subdir)
        if not os.path.exists(archive_path):
            os.mkdir(archive_path)
        # archive all but the newest N files from each group
        count_archived = 0
        for prefix, files in groups.items():
            files = files[BridgeLogs.number_log_files_to_keep:]
            for f in files:
                try:
                    shutil.move(f.full_path, os.path.join(archive_path, f.name))
                except Exception as ex:
                    logger.warning(str(ex))
                count_archived += 1
        return count_archived, archive_path

    @staticmethod
    def archive_log_files_by_date(logger: StreamLogger, log_folder, log_files: List[BridgeLogFile], number_to_archive: int):
        archive_subdir = "archive_logs"
        log_files.sort(key=lambda x: x.mod_time)

        archive_path = os.path.join(log_folder, archive_subdir)
        if not os.path.exists(archive_path):
            os.mkdir(archive_path)
        # archive all but the newest N files from each group
        count = 0
        for f in log_files:
            try:
                shutil.move(f.full_path, os.path.join(archive_path, f.name))
            except Exception as ex:
                logger.warning(str(ex))
            count += 1
            if number_to_archive == count:
                break
        return count, archive_path


class BridgeContainerLogsPath:
    @staticmethod
    def get_logs_path(rpm_source: str, user_as_tableau: bool):
        home = "/home/tableau" if user_as_tableau else "/root"
        beta = "_Beta" if rpm_source == BridgeRpmSource.devbuilds else ""
        return f"{home}/Documents/My_Tableau_Bridge_Repository{beta}/Logs"
