import json
import os.path
from typing import Dict

import yaml

from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.tool_functions import camelcase_to_underscore


class PromptHandler(object):

    def __init__(self, default_prompt_dir: str = "config/prompts"):
        self._default_prompt_dir: str = default_prompt_dir
        self._prompt_dict: Dict[str, str] = {}

    def add_file_prompts(self, name: str, to_underscore: bool = True):
        if to_underscore:
            name: str = camelcase_to_underscore(name)

        class_path = os.path.join(self._default_prompt_dir, name)
        if os.path.exists(f"{class_path}.yaml"):
            with open(f"{class_path}.yaml") as f:
                prompt_language_dict = yaml.load(f, yaml.FullLoader)
        elif os.path.exists(f"{class_path}.json"):
            with open(f"{class_path}.json") as f:
                prompt_language_dict = json.load(f)
        else:
            raise RuntimeError(f"{class_path}.yaml/json is not exists!")

        for key, language_dict in prompt_language_dict.items():
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
