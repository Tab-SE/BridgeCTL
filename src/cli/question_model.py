from src.cli.app_logger import LOGGER

class Question:
    answer: str = None
    params: dict = None
    root_app = None  # Keep root calling root_app

    def __init__(self, root_app):
        self.root_app = root_app

    def asking(self, **kwargs):
        if kwargs:
            self.params = kwargs

        self.ask()
        while not self.validate_and_print():
            self.ask()

        return self.answer

    def validate_and_print(self):
        if not hasattr(self, 'validate'):
            return True
        error = self.validate()
        if error is not None:
            LOGGER.error(error)
            return False
        return True