import os
import yaml
import streamlit as st
from pathlib import Path

from src.enums import TEMPLATE_DIR
from src.models import CONFIG_DIR


class PromptLibrary:
    """Class to manage loading and accessing LLM prompts from YAML files."""

    def __init__(self):
        self.prompt_type: str = 'bridge_jobs_analysis'
        self.default_llm_prompts_file = TEMPLATE_DIR / 'default_llm_prompts.yml'
        self.user_llm_prompts_file = CONFIG_DIR / 'user_llm_prompts.yml'

        with open(self.default_llm_prompts_file) as f:
            data = yaml.safe_load(f)
            self.default_prompts = data[self.prompt_type]

        if self.user_llm_prompts_file.exists():
            with open(self.user_llm_prompts_file) as f:
                data = yaml.safe_load(f)
                self.user_prompts = data[self.prompt_type]
        else:
            self.user_prompts = {}
    
    def load_prompts(self):
            prompts = self.default_prompts.copy()
            prompts.update(self.user_prompts) # Merge user prompts into default prompts, overwriting any duplicates
            return prompts
    
    def remove_user_prompt(self, prompt_name: str):
        if prompt_name not in self.user_prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found in user prompts")
        del self.user_prompts[prompt_name]
        self.save_user_prompts()
    
    def save_user_prompts(self):
        with open(self.user_llm_prompts_file, 'w') as f:
            yaml.dump({self.prompt_type: self.user_prompts}, f)

class PromptPrep:
    max_prompt_token_length_o1mini = 128000

    @staticmethod
    def estimate_tokens(prompt: str) -> int:
        """Estimate the number of tokens in a string."""
        tokens_per_char = 0.25  # rough estimate of tokens per character for English text
        return int(len(prompt) * tokens_per_char)