import datetime
import re

from memory_scope.constants.language_constants import WEEKDAYS
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger


class DatetimeHandler(object):

    def __init__(self, dt: datetime.datetime | str | int | float = None):
        if isinstance(dt, str | int | float):
            if isinstance(dt, str):
                dt = float(dt)
            self._dt: datetime.datetime = datetime.datetime.fromtimestamp(dt)
        elif isinstance(dt, datetime.datetime):
            self._dt: datetime.datetime = dt
        else:
            self._dt: datetime.datetime = datetime.datetime.now()

        self._dt_info_dict: dict | None = None
        self.logger = Logger.get_logger()

    def _parse_dt_info(self):
        return {
            "year": self._dt.year,
            "month": self._dt.month,
            "day": self._dt.day,
            "hour": self._dt.hour,
            "minute": self._dt.minute,
            "second": self._dt.second,
            "week": self._dt.isocalendar().week,
            "weekday": WEEKDAYS[G_CONTEXT.language][self._dt.isocalendar().weekday - 1],
        }

    @property
    def dt_info_dict(self):
        if self._dt_info_dict is None:
            self._dt_info_dict = self._parse_dt_info()
        return self._dt_info_dict

    @staticmethod
    def extract_date_parts_cn(input_string: str):
        # Extending our pattern to handle every/每 as a possible value.
        patterns = {
            'year': r'(\d+|每)年',
            'month': r'(\d+|每)月',
            'day': r'(\d+|每)日',
            'weekday': r'周([一二三四五六日])',
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

    def extract_date_parts(self):
        func_name = f"extract_date_parts_{G_CONTEXT.language}"
        if not hasattr(self, func_name):
            self.logger.warning(f"language={G_CONTEXT.language} needs to complete extract_date_parts function!")
            return {}
        return getattr(self, func_name)()

    def datetime_format(self, dt_format: str = "%Y%m%d"):
        return self._dt.strftime(dt_format)

    def string_format(self, string_format: str):
        return string_format.format(**self.dt_info_dict)
