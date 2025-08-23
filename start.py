import colorama

colorama.init(autoreset=True)  # After each print(), reset to default console foreground color.

from src.cli.version_check import check_python_requirements

check_python_requirements()

from src.cli import app_class

if __name__ == "__main__":
    app = app_class.AppClass()
    app.run()
