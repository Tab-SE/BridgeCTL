import datetime
import glob
import logging
import os
import pathlib
import re
import traceback
from datetime import date

from src.enums import LOG_DIR
from src.models import LoggerInterface
from colorama import Fore

from rich.console import Console


class AppLogger(LoggerInterface):
    _logger = None
    # LOG_DIR = str(pathlib.Path(__file__).parent.parent.parent / "log")
    current_log_file = ""
    BG_LOG_PREFIX = "BACKGROUND "

    def __init__(self):
        today = date.today()
        _date = today.strftime("%Y-%m-%d")

        self.console = Console()

        # Create log path
        if not os.path.exists(LOG_DIR):
            try:
                os.mkdir(LOG_DIR)
            except Exception as e:
                print(Fore.RED + f"Can't create {LOG_DIR}/ for logging - {e}")

        L = logging.getLogger('bridgectl')
        L.setLevel("INFO")

        self.current_log_file = f"{LOG_DIR}/bridgectl_{_date}.log"

        fh = logging.FileHandler(self.current_log_file)
        fh.setLevel("INFO")

        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        fh.setFormatter(formatter)

        L.addHandler(fh)
        self._logger = L

        # Do logs cleanup on initialization
        self._cleanup()

    def _cleanup(self):
        log_age_to_keep = 15
        # log_age_to_keep in days
        today_date = date.today()
        log_files_list = glob.glob(f"{LOG_DIR}/bridgectl_*.log")
        if len(log_files_list) < 2:
            # There is no logs or only current
            return

        try:
            for log_file in log_files_list:
                match = re.match(r"bridgectl_(\d{4}-\d{2}-\d{2}).log", os.path.basename(log_file))
                if not match:
                    continue
                file_date = datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date()
                delta = (today_date - file_date).days
                if delta > log_age_to_keep and log_file != self.current_log_file:
                    self.info_file_only(f"Removing {log_file} - more then {log_age_to_keep} days old")
                    os.remove(log_file)
        except Exception as e:
            print(f"Error during logs cleanup - {e}")

    def info(self, msg = "", color=None, is_background: bool = False):
        if is_background:
            self.info_file_only(self.BG_LOG_PREFIX + msg)
            return

        print_msg = color + str(msg) + Fore.RESET if color else msg
        print(print_msg)
        self._logger.info(str(msg))

    def info_rich(self, msg, is_background: bool = False, **kwargs):
        if is_background:
            self.info_file_only(self.BG_LOG_PREFIX + msg)
            return

        self.console.print(msg, **kwargs)
        self._logger.info(str(msg))

    def info_file_only(self, msg):
        self._logger.info(msg)

    def usage_log(self, detail: str = ""):
        #FutureDev: log app usage metrics
        pass

    def error(self, msg, ex: Exception = None, is_background: bool = False):
        if ex:
            msg += "\nStacktrace:\n" + traceback.format_exc()
            # msg += "\nStacktrace:\n" + \
            #        '\n'.join(traceback.format_exception(type(ex), ex, ex.__traceback__))

        if is_background:
            self._logger.error(self.BG_LOG_PREFIX + msg)
            return

        print(Fore.RED + str(msg) + Fore.RESET)
        self._logger.error(str(msg))

    def warning(self,  msg: str, color=Fore.YELLOW, is_background: bool = False):
        if is_background:
            self._logger.warning(self.BG_LOG_PREFIX + msg)
            return

        print_msg = color + "WARNING: " + str(msg) + Fore.RESET if color else "WARNING: " + msg
        print(print_msg)
        self._logger.warning(str(msg))

    def invalid(self,  msg: str, color=Fore.YELLOW):
        """ User data invalid messages (user's fault something went wrong)"""
        print_msg = color + "INVALID: " + str(msg) + Fore.RESET if color else "INVALID: " + msg
        print(print_msg)
        self._logger.info(str(msg))


# Init the new logger
LOGGER = AppLogger()
