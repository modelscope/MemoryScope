import re
from datetime import datetime
from importlib import import_module
from typing import Dict, List

from constants.common_constants import WEEKDAYS

from enumeration.message_role_enum import MessageRoleEnum


def under_line_to_hump(underline_str):
    sub = re.sub(r'(_\w)', lambda x: x.group(1)[1].upper(), underline_str)
    return sub[0:1].upper() + sub[1:]


def parse_response_text_v1(response_text: str) -> dict:
    """
    parse text like:
    <1> <AAA>
    <2> <BBB> ddd
    <4> <CCC> dddd<555>

    result = {1: "AAA", 2: "BBB", 4: "CCC"}
    """
    result_dict: Dict[int, str] = {}

    # 确保第一个数字，后面是string
    matches = re.findall(r'<(\d+)>\s*<([^>]+)>', response_text.strip())

    # matches 为空返回
    for key, value in matches:
        result_dict[int(key)] = value

    return result_dict


def parse_response_text_v2(response_text: str) -> Dict[int, List[str]]:
    """
    parse text like:
    XXX
    <1> <AAA> <222>
    <2> <BBB>
    <4,5> <CCC>

    result = {1: ["AAA", "222"], 2: "BBB", 4: "CCC"}
    """
    result_dict: Dict[int, List[str]] = {}
    for line in response_text.strip().split("\n"):
        if "> <" not in line:
            continue
        ll = [x.removeprefix("<").removesuffix(">") for x in line.strip().split("> <")]
        idx: str = ll[0]
        values: List[str] = ll[1:]
        if idx.isdigit():
            idx_int = int(idx)
        else:
            idx_split = idx.split(",")
            if len(idx_split) == 0:
                continue
            idx = idx_split[0]
            if idx.isdigit():
                idx_int = int(idx)
            else:
                continue
        if values:
            result_dict[idx_int] = values

    return result_dict


def parse_response_text_v3(response_text: str) -> List[List[str]]:
    """
    parse text like:
    XXX
    <1> <AAA>
    <2c> <BBB>
    <41> <CCC> <BBB>

    result = [["1", "AAA"], ["2c", "BBB"], ["41", "CCC", "BBB"]]
    """
    result_list: List[List[str]] = []
    for line in response_text.strip().split("\n"):
        if "> <" not in line:
            continue
        ll = [x.removeprefix("<").removesuffix(">") for x in line.strip().split("> <")]
        result_list.append(ll)
    return result_list


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


def extract_date_parts(input_string: str):
    # Extending our pattern to handle "每" (every) as a possible value.
    patterns = {
        'year': r'(\d+|每)年',
        'month': r'(\d+|每)月',
        'day': r'(\d+|每)日',
        'weekday': r'周([一二三四五六日])?',
        'hour': r'(\d+)点'
    }
    weekday_dict = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7}
    extracted_data = {}

    # Search for patterns in the input string and populate the dictionary
    for key, pattern in patterns.items():
        match = re.search(pattern, input_string)
        if match:  # If there is a match, include it in the output dictionary
            if match.group(1) == "每":
                extracted_data[key] = -1
            elif match.group(1) in weekday_dict.keys():
                extracted_data[key] = weekday_dict[match.group(1)]
            else:
                extracted_data[key] = int(match.group(1))
    return extracted_data


def time_to_formatted_str(time: datetime | str | int | float = None,
                          date_format: str = "%Y%m%d",  # e.g. %Y%m%d -> "20240528", add %H:%M:%S
                          string_format: str = "") -> str:
    if isinstance(time, str | int | float):
        if isinstance(time, str):
            time = float(time)
        current_dt = datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        current_dt = time
    else:
        current_dt = datetime.now()

    return_str = ""
    if date_format:
        return_str = current_dt.strftime(date_format)
    elif string_format:
        return_str = string_format.format(**get_datetime_info_dict(current_dt))

    return return_str


def init_instance_by_config(config: dict|object, default_module_path: str = None, try_kwargs: dict = {}, accept_types: type = None):
    if isinstance(config, accept_types):
        return config

  import_module(config.pop("path", default_module_path))
    clazz = getattr(module, config.pop("name"))
    try:
        return clazz(**config, **try_kwargs)
    except:
        return clazz(**config)


def init_instance_by_config_v2(config: dict, default_clazz_path: str = "", suffix_name: str = "", **kwargs):
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
