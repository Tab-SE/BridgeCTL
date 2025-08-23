import traceback

from src.models import LoggerInterface
import streamlit as st

class StreamLogger(LoggerInterface):
    def __init__(self, container = None, progress_bar = None):
        self.container = container
        self.progress_bar = progress_bar

    def info(self, msg = ""):
        if self.container:
            self.container.text(msg)
        else:
            st.text(msg)

    def warning(self,  msg: str):
        if self.container:
            self.container.warning(msg)
        else:
            st.warning(msg)

    def error(self, msg, ex: Exception = None):
        # ex_string = traceback.print_exc()
        if self.container:
            self.container.error(msg)
        else:
            st.error(f"ERROR: {msg}")

    def progress(self, value: int):
        if self.progress_bar:
            self.progress_bar.progress(value)

class StreamLoggerRich:
    def __init__(self, container):
        self.container = container

    def markdown(self, msg = ""):
        self.container.markdown(msg)

    def info(self, msg = ""):
        self.container.info(msg)

    def warning(self,  msg: str):
        self.container.warning(msg)

    def success(self,  msg: str):
        self.container.success(msg)

    def text(self,  msg: str):
        self.container.text(msg)

    def text_area(self,  label:str, msg: str, height=300):
        self.container.text_area(label, msg, height=height, disabled=True)

    def code(self,  msg: str, language: str):
        self.container.code(msg, language = language)

    def error(self, msg, ex: Exception = None):
        exc_traceback = traceback.format_exception(type(ex), ex, ex.__traceback__)
        traceback_str = ''.join(exc_traceback)
        self.container.error(f"{msg}\n{traceback_str}" )
