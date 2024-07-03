import datetime
import re
from typing import Dict

from memory_scope.constants.language_constants import WEEKDAYS
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger


class DatetimeHandler(object):
    logger = Logger.get_logger()

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

    @classmethod
    def extract_date_parts_cn(cls, input_string: str) -> dict:
        # Extending our pattern to handle every/每 as a possible value.
        patterns = {
            "year": r"(\d+|每)年",
            "month": r"(\d+|每)月",
            "day": r"(\d+|每)日",
            "weekday": r"周([一二三四五六日])",
            "hour": r"(\d+)点"
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

    @classmethod
    def extract_date_parts_en(cls, input_string: str) -> dict:
        date_info = {
            "year": -1,
            "month": -1,
            "day": -1,
            "hour": -1,
            "minute": -1,
            "second": -1,
            "weekday": -1
        }

        # Patterns to extract the parts of the date/time
        # Patterns to extract the parts of the date/time
        patterns = {
            "year": r"\b(\d{4})\b",
            "month": r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
            "day_month_year": r"\b(?P<month>January|February|March|April|May|June|July|August|September|October|November|December) (?P<day>\d{1,2}),? (?P<year>\d{4})\b",
            "day_month": r"\b(?P<month>January|February|March|April|May|June|July|August|September|October|November|December) (?P<day>\d{1,2})\b",
            "hour_12": r"\b(\d{1,2})\s*(AM|PM|am|pm)\b",
            "hour_24": r"\b(\d{1,2}):(\d{2}):(\d{2})\b"
        }

        month_mapping = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12
        }

        weekday_mapping = {
            "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
            "Friday": 5, "Saturday": 6, "Sunday": 7
        }

        day_month_year_match = re.search(patterns["day_month_year"], input_string)
        if day_month_year_match:
            date_info["year"] = int(day_month_year_match.group("year"))
            date_info["month"] = month_mapping[day_month_year_match.group("month")]
            date_info["day"] = int(day_month_year_match.group("day"))

        # Extract month and day without year
        elif date_info["year"] == -1:
            day_month_match = re.search(patterns["day_month"], input_string)
            if day_month_match:
                date_info["month"] = month_mapping[day_month_match.group("month")]
                date_info["day"] = int(day_month_match.group("day"))

        # Extract year
        if date_info["year"] == -1:
            year_match = re.search(patterns["year"], input_string)
            if year_match:
                date_info["year"] = int(year_match.group(0))

        # Extract month
        if date_info["month"] == -1:
            month_match = re.search(patterns["month"], input_string)
            if month_match:
                date_info["month"] = month_mapping[month_match.group(0)]

        # Extract 12-hour format time
        hour_12_match = re.search(patterns["hour_12"], input_string)
        if hour_12_match:
            hour, period = int(hour_12_match.group(1)), hour_12_match.group(2).lower()
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            date_info["hour"] = hour

        # # Extract 24-hour format time
        # hour_24_match = re.search(patterns["hour_24"], input_string)
        # if hour_24_match:
        #     date_info["hour"] = int(hour_24_match.group(1))
        #     date_info["minute"] = int(hour_24_match.group(2))
        #     date_info["second"] = int(hour_24_match.group(3))

        # Extract weekday
        for week_day, value in weekday_mapping.items():
            if week_day in input_string:
                date_info["weekday"] = value
                break

        return date_info

    @classmethod
    def extract_date_parts(cls, input_string: str) -> dict:
        func_name = f"extract_date_parts_{G_CONTEXT.language}"
        if not hasattr(cls, func_name):
            cls.logger.warning(f"language={G_CONTEXT.language} needs to complete extract_date_parts func!")
            return {}
        return getattr(cls, func_name)(input_string=input_string)

    @classmethod
    def format_time_by_extract_time_cn(cls, extract_time_dict: Dict[str, str], meta_data: Dict[str, str]) -> str:
        cn_key_dict = {"year": "年", "month": "月", "day": "日", "weekday": ""}
        format_time_str = ""
        for key, value_cn in cn_key_dict.items():
            if key in extract_time_dict and key in meta_data:
                value = meta_data[key]
                if value_cn:
                    if value == "-1":
                        value = "每"
                    format_time_str += f"{value}{value_cn}"
                else:
                    format_time_str += value
        return format_time_str

    @classmethod
    def format_time_by_extract_time(cls, extract_time_dict: Dict[str, str], meta_data: Dict[str, str]) -> str:
        func_name = f"format_time_by_extract_time_{G_CONTEXT.language}"
        if not hasattr(cls, func_name):
            cls.logger.warning(f"language={G_CONTEXT.language} needs to complete format_time_by_extract_time func!")
            return ""
        return getattr(cls, func_name)(extract_time_dict, meta_data)

    def datetime_format(self, dt_format: str = "%Y%m%d"):
        return self._dt.strftime(dt_format)

    def string_format(self, string_format: str):
        return string_format.format(**self.dt_info_dict)

    @property
    def timestamp(self) -> int:
        return int(self._dt.timestamp())
