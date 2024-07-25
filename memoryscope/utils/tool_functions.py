import hashlib
import random
import re
import time
from copy import deepcopy
from importlib import import_module
from typing import List

import pyfiglet
from termcolor import colored

from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.scheme.message import Message

ALL_COLORS = ["red", "green", "yellow", "blue", "magenta", "cyan", "light_grey", "light_red", "light_green",
              "light_yellow", "light_blue", "light_magenta", "light_cyan", "white"]


def underscore_to_camelcase(name: str, is_first_title: bool = True) -> str:
    """
    Converts a underscore_notation string to CamelCase.

    Args:
        name (str): The underscore_notation string to be converted.
        is_first_title (bool): Title the first word or not. Defaults to True

    Returns:
        str: A CamelCase formatted string.
    """
    name_split = name.split("_")
    if is_first_title:
        return "".join(x.title() for x in name_split)
    else:
        return name_split[0] + ''.join(x.title() for x in name_split[1:])


def camelcase_to_underscore(name: str) -> str:
    """
    Converts a CamelCase string to underscore_notation.

    Args:
        name (str): The CamelCase formatted string to be converted.

    Returns:
        str: A converted string in underscore_notation.
    """
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def init_instance_by_config(config: dict,
                            default_class_path: str = "memoryscope",
                            suffix_name: str = "",
                            **kwargs):
    """
    Initialize an instance of a class specified in the configuration dictionary.

    This function dynamically imports a class from a module path, allowing for 
    user-defined classes or default paths. It supports adding a suffix to the 
    class name, merging additional keyword arguments with the config, and handling 
    nested module paths.

    Args:
        config (dict): A dictionary containing the configuration, including 
                       the 'class' key that specifies the class's module path.
        default_class_path (str, optional): The default module path prefix 
                                            to use if not explicitly defined in 
                                            'config'. Defaults to "memory_scope".
        suffix_name (str, optional): A string to append to the class name, 
                                     ensuring the final class name ends with it.
                                     Defaults to "".
        **kwargs: Additional keyword arguments to pass to the class constructor.

    Returns:
        instance: An instance initialized with the provided config and kwargs.
    """

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


def prompt_to_msg(system_prompt: str,
                  few_shot: str,
                  user_query: str,
                  concat_system_prompt: bool = True) -> List[Message]:
    """
    Converts input strings into a structured list of message objects suitable for AI interactions.

    Args:
        system_prompt (str): The system-level instruction or context.
        few_shot (str): An example or demonstration input, often used for illustrating expected behavior.
        user_query (str): The actual user query or prompt to be processed.
        concat_system_prompt(bool): Concat system prompt again or not in the user message.
            A simple method to improve the effectiveness for some LLMs. Defaults to True.

    Returns:
        List[Message]: A list of Message objects, each representing a part of the conversation setup.
    """
    if concat_system_prompt:
        user_message = Message(
            role=MessageRoleEnum.USER.value,
            content="\n".join(
                [x.strip() for x in [few_shot, system_prompt, user_query]]
            ),
        )
    else:
        user_message = Message(
            role=MessageRoleEnum.USER.value,
            content="\n".join([x.strip() for x in [few_shot, user_query]]),
        )

    return [
        Message(role=MessageRoleEnum.SYSTEM.value, content=system_prompt.strip()),  # System message
        user_message
        # User message combining few shot, system prompt, and user query
    ]


def char_logo(words: str, seed: int = time.time_ns(), color=None):
    """
    Render the context of logo with colors

    Args:
        words: The context of logo.
        seed: The random seed which generates colors if there is no specific color. Defaults to the current timestamp.
        color: The specific color. Defaults to None.

    Returns:
        A rendered logo
    """
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


def md5_hash(input_string: str) -> str:
    """
    Computes a MD5 hash of the given input string.

    Args:
        input_string (str): The string for which the MD5 hash needs to be computed.

    Returns:
        str: A hexadecimal MD5 hash representation.
    """
    m = hashlib.md5()
    m.update(input_string.encode('utf-8'))
    return m.hexdigest()


def contains_keyword(text, keywords) -> bool:
    """
    Checks if the given text contains any of the specified keywords, ignoring case.

    Args:
        text (str): The text to search within.
        keywords (List[str]): A list of keywords to look for in the text.

    Returns:
        bool: True if any keyword is found in the text, False otherwise.
    """
    escaped_keywords = map(re.escape, keywords)
    pattern = re.compile('|'.join(escaped_keywords), re.IGNORECASE)
    return pattern.search(text) is not None