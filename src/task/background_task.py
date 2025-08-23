import threading
import logging
from pathlib import Path
from src.models import LoggerInterface


class BackgroundTask:
    def __init__(self, background_task):
        self.thread = None
        self.stop_event = threading.Event()
        self.logger = BG_LOGGER
        self.background_task = background_task

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self.background_task)
            self.thread.daemon = True #if main program exits, stop thread.
            self.thread.start()
        else:
            self.logger.info("can't start because background task is already running")

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()

    def check_status(self):
        if self.thread and self.thread.is_alive():
            return True
        else:
            return False

class BgLogger(LoggerInterface):
    def __init__(self):
        self.logger = logging.getLogger('BackgroundTaskManager')
        self.logger.setLevel(logging.INFO)
        self.log_file_path = Path(__file__).parent.parent.parent / 'log' / 'background_task.log'
        handler = logging.FileHandler(self.log_file_path)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def info(self, msg=""):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg, ex: Exception = None):
        self.logger.error(msg, exc_info=ex)

BG_LOGGER = BgLogger()