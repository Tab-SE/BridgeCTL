import sys
import time

import psutil

from src import os_type
from src.cli.app_logger import LOGGER
from src.os_type import OsType


class PsLib:
    @staticmethod
    def find_process_id_by_name(startup_command):
        """
        Get a list of all the PIDs of a all the running process whose name contains
        the given string processName
        """
        for proc in psutil.process_iter():
           try:
               pinfo = proc.as_dict(attrs=['pid', 'name', 'cmdline'])
               c =pinfo['cmdline']
               if c and startup_command in ' '.join(c):
                   return pinfo['pid']
           except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
               pass
        return None

    @staticmethod
    def kill_process(pid):
        if not isinstance(pid, int) or not pid > 10:
            raise ValueError(f"pid '{pid}' is invalid")
        try:
            process = psutil.Process(pid)
            process.kill()
        except psutil.NoSuchProcess:
            raise Exception(f"No process found with PID {pid}.")
        except psutil.AccessDenied:
            raise Exception(f"Permission denied to kill process with PID {pid}.")

    @staticmethod
    def stop_streamlit():
        entry_script = sys.argv[0]
        if entry_script == "Home.py":
            LOGGER.info("not stopping Streamlit UI because current process is Streamlit UI")
            return
        LOGGER.info("stopping Streamlit UI")
        proc_pid = PsLib.find_process_id_by_name("streamlit run Home.py")
        if not proc_pid:
            proc_pid = PsLib.find_process_id_by_name("streamlit run Web.py") #maybe this is not needed.
        if not proc_pid:
            LOGGER.info("process not found")
        else:
            PsLib.kill_process(proc_pid)
            LOGGER.info(f"  UI process stopped")
            if os_type.current_os() == OsType.win:
                time.sleep(5)