import hashlib
import random
import re
import time
from copy import deepcopy
from importlib import import_module

import pyfiglet
from termcolor import colored

from memory_scope.enumeration.message_role_enum import MessageRoleEnum

ALL_COLORS = ["red", "green", "yellow", "blue", "magenta", "cyan", "light_grey", "light_red", "light_green",
              "light_yellow", "light_blue", "light_magenta", "light_cyan", "white"]


def underscore_to_camelcase(name: str, is_first_title: bool = True):
    name_split = name.split("_")
    if is_first_title:
        return "".join(x.title() for x in name_split)
    else:
        return name_split[0] + ''.join(x.title() for x in name_split[1:])


def camelcase_to_underscore(name: str):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def init_instance_by_config(config: dict,
                            default_class_path: str = "memory_scope",
                            suffix_name: str = "",
                            **kwargs):
    config_copy = deepcopy(config)
    origin_class_path: str = config_copy.pop("class")
    if not origin_class_path:
        raise RuntimeError("empty class path!")
    user_defined: bool = config_copy.pop("user_defined", False)

    class_name_split = origin_class_path.split(".")
    class_name: str = class_name_split[-1]
    if suffix_name and not class_name.lower().endswith(suffix_name.lower()):
        class_name = f"{class_name}_{suffix_name}"
        class_name_split[-1] = class_name

    class_paths = []
    if not user_defined and default_class_path and not origin_class_path.startswith(default_class_path):
        class_paths.append(default_class_path)
    class_paths.extend(class_name_split)
    module = import_module(".".join(class_paths))

    cls_name = underscore_to_camelcase(class_name)
    config_copy.update(kwargs)
    return getattr(module, cls_name)(**config_copy)


def prompt_to_msg(system_prompt: str, few_shot: str, user_query: str):
    return [
        {
            "role": MessageRoleEnum.SYSTEM.value,
            "content": system_prompt.strip(),
        },
        {
            "role": MessageRoleEnum.USER.value,
            "content": "\n".join(
                [x.strip() for x in [few_shot, system_prompt, user_query]]
            ),
        },
    ]


def char_logo(words: str, seed: int = time.time_ns(), color=None):
    font = pyfiglet.Figlet()
    rendered_text = font.renderText(words)
    colored_lines = []
    all_colors = ALL_COLORS.copy()
    random.seed = seed
    for line in rendered_text.splitlines():
        line_color = color
        if line_color is None:
            random.shuffle(all_colors)
            line_color = all_colors[0]
        colored_line = ""
        for char in line:
            colored_char = colored(char, line_color, attrs=['bold'])
            colored_line += colored_char
        colored_lines.append(colored_line)
    return colored_lines


def md5_hash(input_string: str):
    m = hashlib.md5()
    m.update(input_string.encode('utf-8'))
    return m.hexdigest()


def contains_keyword(text, keywords):
    escaped_keywords = map(re.escape, keywords)
    pattern = re.compile('|'.join(escaped_keywords), re.IGNORECASE)
    return pattern.search(text) is not None
