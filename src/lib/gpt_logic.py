from openai import OpenAI
import os
from datetime import datetime
from pathlib import Path

from src.enums import LOG_DIR


class ChatGPTClient:
    def __init__(self, api_key: str):
        base_url = None
        if not api_key:
            raise Exception("api_key is required")        
        self.model = 'gpt-4o-mini'
        self.is_initialized = False
        self.client = OpenAI(api_key=api_key, base_url = base_url)
        self.is_initialized = True

    def ask(self, prompt):
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing Tableau Bridge logs and summarizing interesting findings like number of errors and what the solutions to the errors is."},
                {"role": "user", "content": prompt}],
            temperature=0,
            stream=True,
            n=1,
        )
        # self.log_result(prompt, completion)
        return completion

    def code_genie_settings(self):
        from src.internal.devbuilds.devbuilds_const import CodeGenieSettings
        base_url = CodeGenieSettings.code_genie_url
        api_key = CodeGenieSettings.code_genie_api_key
        self.model = CodeGenieSettings.code_genie_model
        
    # def log_result(self, prompt: str, response: str) -> None:
    #     """Log the prompt and completion to a file."""
    #     date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     log_file = LOG_DIR / f"llm_results_{date_str}.log"
    #
    #     with open(log_file, "w") as f:
    #         f.write("=== PROMPT ===\n")
    #         f.write(prompt + "\n\n")
    #         f.write("=== RESPONSE ===\n")
    #         f.write(response)
    #         f.write("\n")

    def log_result(self, prompt: str, completion_stream) -> None:
        """Log the prompt and completion to a file."""
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"llm_results_{date_str}.log"

        with open(log_file, "w") as f:
            f.write("=== PROMPT ===\n")
            f.write(prompt + "\n\n")
            f.write("=== RESPONSE ===\n")
            for chunk in completion_stream:
                if hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        f.write(content)
            f.write("\n")