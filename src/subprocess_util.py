import subprocess
from typing import List
from dataclasses import dataclass
from pathlib import Path

from src.models import LoggerInterface
from src.os_type import OsType, current_os


class SubProcess:
    def __init__(self, logger: LoggerInterface):
        self.logger = logger

    def run_cmd(self, cmds: List[str], name: str = '', cwd: str or Path = None, secrets: List[str] = None, display_output = False, raise_on_fail = True):
        self.logger.info(f'\nSUBPROCESS START {name}')
        sep = " && " if current_os() == OsType.win else "; "
        cmd = sep.join(cmds)
        self.sanitize_output(cmd, secrets)
        process = subprocess.run(cmd, cwd=cwd, capture_output=True, shell=True, universal_newlines=True)
        self.log_process_output(process, secrets, display_output)
        if process.returncode != 0 and raise_on_fail:
            raise Exception(f"subprocess command failed: {name}")
        return process

    def run_cmd_text(self, cmd: str, name: str = '', cwd: str or Path = None, secrets: List[str] = None, display_output = False, raise_on_fail = True):
        self.logger.info(f'\nSUBPROCESS START {name}')
        self.sanitize_output(cmd, secrets)
        process = subprocess.run(cmd, cwd=cwd, capture_output=True, shell=True, universal_newlines=True)
        self.log_process_output(process, secrets, display_output)
        if process.returncode != 0 and raise_on_fail:
            raise Exception(f"subprocess command failed: {name}")
        return process

    def log_process_output(self, process, secrets, display_output):
        if process.returncode != 0 or display_output:
            self.logger.info('~~~~~~stdout~~~~~~')
            self.sanitize_output(process.stdout, secrets)
            if process.stderr:
                self.logger.info('~~~~~~stderr~~~~~~')
                self.sanitize_output(process.stderr, secrets)
        code = "success" if process.returncode == 0 else f"failed, return code: {process.returncode}"
        self.logger.info(f'SUBPROCESS DONE {code}')


    def sanitize_output(self, content: str, secrets: List[str]):
        if secrets:
            for secret in secrets:
                content = content.replace(secret, "****")
        if current_os() == OsType.win:
            c = content.replace(' && ', ' && \n')
        else:
            c = content.replace('; ', '; \n')
        if len(c) > 0:
            self.logger.info(c)

    @staticmethod
    def run_cmd_light(cmd: str, throw_on_error = False):
        process = subprocess.run(cmd, capture_output=True, check=throw_on_error, shell=True, universal_newlines=True)
        return process.stdout, process.stderr, process.returncode

    @staticmethod
    def run_popen(cmd: str, cwd: str | Path):
        process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        return process


@dataclass
class MockProcess:
    returncode: int = 0
    stdout = ""
    stderr = ""
