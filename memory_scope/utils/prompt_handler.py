import json
import os.path
from typing import Dict

import yaml

from memory_scope.utils.global_context import G_CONTEXT


class PromptHandler(object):

    def __init__(self, class_path: str, prompt_file: str = "", prompt_dict: dict = None, **kwargs):
        self._class_path: str = class_path
        self._prompt_dict: Dict[str, str] = {}

        file_path = self._class_path.strip(".py")
        self.add_prompt_file(file_path)

        if prompt_file:
            self.add_prompt_file(prompt_file)

        if prompt_dict:
            self.add_prompt_dict(prompt_dict)

    def add_prompt_file(self, file_path: str):
        if os.path.exists(f"{file_path}.yaml"):
            with open(f"{file_path}.yaml") as f:
                prompt_dict = yaml.load(f, yaml.FullLoader)
        elif os.path.exists(f"{file_path}.json"):
            with open(f"{file_path}.json") as f:
                prompt_dict = json.load(f)
        else:
            raise RuntimeError(f"{file_path}.yaml/json is not exists!")

        self.add_prompt_dict(prompt_dict)

    def add_prompt_dict(self, prompt_dict: dict):
        for key, language_dict in prompt_dict.items():
            prompts = language_dict.get(G_CONTEXT.language)
            if not prompts:
                raise RuntimeError(f"{key}.prompt.{G_CONTEXT.language} is empty!")
            self._prompt_dict[key] = prompts

    @property
    def prompt_dict(self):
        return self._prompt_dict

    def __getitem__(self, key: str):
        return self._prompt_dict[key]

    def __setitem__(self, key: str, value: str):
        self._prompt_dict[key] = value

    def __getattr__(self, key: str):
        return self._prompt_dict[key]
