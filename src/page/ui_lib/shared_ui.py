import os
import subprocess

from src.cli.app_config import APP_CONFIG


class SharedUi:
    @staticmethod
    def show_app_version(cont, inc_dir: bool = False):
        # cont.text("")
        # cont.text("")
        cont.text("")
        # cont2 = cont.columns(2)[0].container(border=True)
        s = f"version {APP_CONFIG.app_version} downloaded from {APP_CONFIG.target_github_repo}"
        cont.text(s)
        if APP_CONFIG.is_internal_build():
            cont.text("Internal devbuilds supported: True")
        if inc_dir:
            cont.text(f"working directory: {os.getcwd()}")
        if not APP_CONFIG.is_internal_build():
            cont.markdown(
                f"""\n\n\n*Terms of Use*: This utility is community supported. 
                Please log any feature requests or bugs on [github discussions]({APP_CONFIG.discussions_url()}).
                Additional resources: Tableau Community Forums and the [DataDev Slack](https://tableau-datadev.slack.com/archives/C07TTGRTLP9). 
                BridgeCTL [License Terms]({APP_CONFIG.base_url()}/blob/main/LICENSE.txt).""")

    @staticmethod
    def stream_subprocess_output(command, cont):
        def generator():
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, universal_newlines=True)
            for line in process.stdout:
                yield line.rstrip() + '  \n'
            process.stdout.close()
            process.wait()
            if process.returncode != 0:
                error_message = process.stderr.read()
                cont.error(f"Error: {error_message}")

        cont.write_stream(generator)
