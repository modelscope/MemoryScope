import hashlib
import random
import re
import time
from copy import deepcopy
from datetime import datetime
from importlib import import_module

import pyfiglet
from termcolor import colored, COLORS

from memory_scope.constants.common_constants import WEEKDAYS
from memory_scope.enumeration.message_role_enum import MessageRoleEnum


def under_line_to_hump(underline_str):
    sub = re.sub(r"(_\w)", lambda x: x.group(1)[1].upper(), underline_str)
    return sub[0:1].upper() + sub[1:]


def init_instance_by_config(config: dict, default_class_path: str = "memory_scope", suffix_name: str = "", **kwargs):
    config_copy = deepcopy(config)
    origin_class_path: str = config_copy.pop("class")
    if not origin_class_path:
        raise RuntimeError("empty class path!")

    class_name_split = origin_class_path.split(".")
    class_name: str = class_name_split[-1]
    if suffix_name and not class_name.lower().endswith(suffix_name.lower()):
        class_name = f"{class_name}_{suffix_name}"
        class_name_split[-1] = class_name

    class_paths = []
    if default_class_path and not origin_class_path.startswith(default_class_path):
        class_paths.append(default_class_path)
    class_paths.extend(class_name_split)
    module = import_module(".".join(class_paths))

    cls_name = under_line_to_hump(class_name)
    config_copy.update(kwargs)
    return getattr(module, cls_name)(**config_copy)


def complete_config_name(config_name: str, suffix: str = ".json"):
    if not config_name.endswith(suffix):
        config_name += suffix
    return config_name


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


def get_datetime_info_dict(parse_dt: datetime):
    return {
        "year": parse_dt.year,
        "month": parse_dt.month,
        "day": parse_dt.day,
        "hour": parse_dt.hour,
        "minute": parse_dt.minute,
        "second": parse_dt.second,
        "week": parse_dt.isocalendar().week,
        "weekday": WEEKDAYS[parse_dt.isocalendar().weekday - 1],
    }


def time_to_formatted_str(dt: datetime | str | int | float = None,
                          date_format: str = "%Y%m%d",  # e.g. %Y%m%d -> "20240528", add %H:%M:%S
                          string_format: str = "") -> str:

    if isinstance(dt, str | int | float):
        if isinstance(dt, str):
            dt = float(dt)
        current_dt = datetime.fromtimestamp(dt)
    elif isinstance(dt, datetime):
        current_dt = dt
    else:
        current_dt = datetime.now()

    return_str = ""
    if date_format:
        return_str = current_dt.strftime(date_format)
    elif string_format:
        return_str = string_format.format(**get_datetime_info_dict(current_dt))

    return return_str


def char_logo(words: str, seed: int = time.time_ns(), color=None):
    font = pyfiglet.Figlet()
    rendered_text = font.renderText(words)
    colored_lines = []
    all_colors = list(COLORS.keys())
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
