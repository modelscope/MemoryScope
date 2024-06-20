import re
from importlib import import_module

from memory_scope.enumeration.message_role_enum import MessageRoleEnum


def under_line_to_hump(underline_str):
    sub = re.sub(r'(_\w)', lambda x: x.group(1)[1].upper(), underline_str)
    return sub[0:1].upper() + sub[1:]


def init_instance_by_config(config: dict, default_clazz_path: str = "", suffix_name: str = "", **kwargs):
    clazz_path = config.pop("clazz")
    if not clazz_path:
        raise RuntimeError("empty clazz_path!")
    clazz_name_split = clazz_path.split(".")
    clazz_name: str = clazz_name_split[-1]
    if suffix_name and not clazz_name.endswith(suffix_name):
        clazz_name = f"{clazz_name}_{suffix_name}"

    # 构造path
    clazz_paths = []
    if default_clazz_path:
        clazz_paths.append(default_clazz_path)
    clazz_paths.extend(clazz_name_split[:-1])
    clazz_paths.append(clazz_name)
    module = import_module(".".join(clazz_paths))

    cls_name = under_line_to_hump(clazz_name)
    return getattr(module, cls_name)(**config, **kwargs)


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
            "content": "\n".join([x.strip() for x in [few_shot, system_prompt, user_query]])
        },
    ]
