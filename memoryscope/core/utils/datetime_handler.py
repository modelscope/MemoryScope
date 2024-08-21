import datetime
import re
from typing import List

from memoryscope.constants.language_constants import WEEKDAYS, DATATIME_WORD_LIST, MONTH_DICT
from memoryscope.enumeration.language_enum import LanguageEnum


class DatetimeHandler(object):
    """
    Handles operations related to datetime such as parsing, extraction, and formatting,
    with support for both Chinese and English contexts including weekday names and
    specialized text parsing for date components.
    """


    def __init__(self, dt: datetime.datetime | str | int | float = None):
        """
        Initialize the DatetimeHandler instance with a datetime object, string, integer, or float representation
        of a timestamp. If no argument is provided, the current time is used.

        Args:
            dt (datetime.datetime | str | int | float, optional):
                The datetime to be handled. Can be a datetime object, a timestamp string, or a numeric timestamp.
                Defaults to None, which sets the instance to the current datetime.

        Attributes:
            self._dt (datetime.datetime): The internal datetime representation of the input.
            self._dt_info_dict (dict | None): A dictionary containing parsed datetime information, defaults to None.
        """
        if isinstance(dt, str | int | float):
            if isinstance(dt, str):
                dt = float(dt)
            self._dt: datetime.datetime = datetime.datetime.fromtimestamp(dt)
        elif isinstance(dt, datetime.datetime):
            self._dt: datetime.datetime = dt
        else:
            self._dt: datetime.datetime = datetime.datetime.now()

        self._dt_info_dict: dict | None = None

    def _parse_dt_info(self, language: LanguageEnum):
        """
        Parses the datetime object (_dt) into a dictionary containing detailed date and time components,
        including language-specific weekday representation.

        Returns:
            dict: A dictionary with keys representing date and time parts such as 'year', 'month',
                  'day', 'hour', 'minute', 'second', 'week', and 'weekday' with respective values.
                  The 'weekday' value is translated based on the current language context.
        """
        return {
            "year": self._dt.year,
            "month": MONTH_DICT[language][self._dt.month - 1],
            "day": self._dt.day,
            "hour": self._dt.hour,
            "minute": self._dt.minute,
            "second": self._dt.second,
            "week": self._dt.isocalendar().week,
            "weekday": WEEKDAYS[language][self._dt.isocalendar().weekday - 1],
        }

    def get_dt_info_dict(self, language: LanguageEnum):
        """
        Property method to get the dictionary containing parsed datetime information.
        If None, initialize using `_parse_dt_info`.

        Returns:
            dict: A dictionary with parsed datetime information.
        """
        if self._dt_info_dict is None:
            self._dt_info_dict = self._parse_dt_info(language=language)
        return self._dt_info_dict

    @classmethod
    def extract_date_parts_cn(cls, input_string: str) -> dict:
        """
        Extracts various components of a date (year, month, day, etc.) from an input string based on Chinese formats.

        This method identifies year, month, day, weekday, and hour components within the input
        string based on predefined patterns. It supports relative terms like '每' (every) and
        translates weekday names into numeric representations.

        Args:
            input_string (str): The Chinese text containing date and time information.

        Returns:
            dict: A dictionary with keys 'year', 'month', 'day', 'weekday', and 'hour',
                  each holding the corresponding extracted value. If a component is not found,
                  it will not be included in the dictionary. For relative terms like '每' (every),
                  the value is set to -1.

        """
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
        """
        Extracts various components of a date (year, month, day, etc.) from an input string based on English formats.

        This method employs regex patterns to identify and parse different date and time elements within the provided
        text. It supports extraction of year, month name, day, 12-hour and 24-hour time formats, and weekdays.

        Args:
            input_string (str): The English text containing date and time information.

        Returns:
            dict: A dictionary containing the extracted date parts with default values of -1 where components are not
            found. Keys include 'year', 'month', 'day', 'hour', 'minute', 'second', and 'weekday'.
        """
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
        patterns = {
            "year": r"\b(\d{4})\b",
            "month": r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
            "day_month_year": r"\b(?P<month>January|February|March|April|May|June|July|August|September|October"
                              r"|November|December) (?P<day>\d{1,2}),? (?P<year>\d{4})\b",
            "day_month": r"\b(?P<month>January|February|March|April|May|June|July|August|September|October|November"
                         r"|December) (?P<day>\d{1,2})\b",
            "hour_12": r"\b(\d{1,2})\s*(AM|PM|am|pm)\b",
            "hour_24": r"\b(\d{1,2}):(\d{2}):(\d{2})\b"
        }

        month_mapping = {
            "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12
        }

        weekday_mapping = {
            "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5, "Saturday": 6, "Sunday": 7
        }

        # Attempt to match full date (day month year)
        day_month_year_match = re.search(patterns["day_month_year"], input_string)
        if day_month_year_match:
            date_info["year"] = int(day_month_year_match.group("year"))
            date_info["month"] = month_mapping[day_month_year_match.group("month")]
            date_info["day"] = int(day_month_year_match.group("day"))

        # If year wasn't found, try matching day and month without year
        elif date_info["year"] == -1:
            day_month_match = re.search(patterns["day_month"], input_string)
            if day_month_match:
                date_info["month"] = month_mapping[day_month_match.group("month")]
                date_info["day"] = int(day_month_match.group("day"))

        # Extract year if not already found
        if date_info["year"] == -1:
            year_match = re.search(patterns["year"], input_string)
            if year_match:
                date_info["year"] = int(year_match.group(0))

        # Extract month if not already found
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

        # Identify weekday
        for week_day, value in weekday_mapping.items():
            if week_day in input_string:
                date_info["weekday"] = value
                break

        return date_info

    @classmethod
    def extract_date_parts(cls, input_string: str, language: LanguageEnum) -> dict:
        """
        Extracts various date components from the input string based on the current language context.

        This method dynamically selects a language-specific function to parse the input string and extract
        date parts such as year, month, day, etc. If the function for current language context does not exist,
        a warning is logged and an empty dictionary is returned.

        Args:
            input_string (str): The string containing date information to be parsed.
            language (str): current language.

        Returns:
            dict: A dictionary containing extracted date components, or an empty dictionary if parsing fails.
        """
        func_name = f"extract_date_parts_{language.value}"
        if not hasattr(cls, func_name):
            # cls.logger.warning(f"language={language.value} needs to complete extract_date_parts func!")
            return {}
        return getattr(cls, func_name)(input_string=input_string)

    @classmethod
    def has_time_word_cn(cls, query: str, datetime_word_list: List[str]) -> bool:
        """
        Check if the input query contains any datetime-related words based on the cn language context.

        Args:
            query (str): The input string to check for datetime-related words.
            datetime_word_list (list[str]): datetime keywords

        Returns:
            bool: True if the query contains at least one datetime-related word, False otherwise.
        """
        contain_datetime = False
        # TODO use re
        for datetime_word in datetime_word_list:
            if datetime_word in query:
                contain_datetime = True
                break
        return contain_datetime

    @classmethod
    def has_time_word_en(cls, query: str, datetime_word_list: List[str]) -> bool:
        """
        Check if the input query contains any datetime-related words based on the en language context.

        Args:
            query (str): The input string to check for datetime-related words.
            datetime_word_list (list[str]): datetime keywords

        Returns:
            bool: True if the query contains at least one datetime-related word, False otherwise.
        """
        contain_datetime = False
        for datetime_word in datetime_word_list:
            datetime_word = datetime_word.lower()
            # TODO fix strip
            if datetime_word in [x.strip().lower().strip(",").strip(".").strip("?").strip(":")
                                 for x in query.split(" ")]:
                contain_datetime = True
                break
        return contain_datetime

    @classmethod
    def has_time_word(cls, query: str, language: LanguageEnum) -> bool:
        func_name = f"has_time_word_{language.value}"
        if not hasattr(cls, func_name):
            # cls.logger.warning(f"language={language.value} needs to complete has_time_word function!")
            return False

        if language not in DATATIME_WORD_LIST:
            # cls.logger.warning(f"language={language.value} is missing in DATATIME_WORD_LIST!")
            return False

        datetime_word_list = DATATIME_WORD_LIST[language]
        return getattr(cls, func_name)(query=query, datetime_word_list=datetime_word_list)

    def datetime_format(self, dt_format: str = "%Y%m%d") -> str:
        """
        Format the stored datetime object into a string based on the provided format.

        Args:
            dt_format (str, optional): The datetime format string. Defaults to "%Y%m%d".

        Returns:
            str: A formatted datetime string.
        """
        return self._dt.strftime(dt_format)

    def string_format(self, string_format: str, language: LanguageEnum) -> str:
        """
        Format the datetime information stored in the instance using a custom string format.

        Args:
            string_format (str): A format string where placeholders are keys from `dt_info_dict`.
            language (str): current language.

        Returns:
            str: A formatted datetime string.
        """
        return string_format.format(**self.get_dt_info_dict(language=language))

    @property
    def timestamp(self) -> int:
        """
        Get the timestamp representation of the stored datetime.

        Returns:
            int: A timestamp value.
        """
        return int(self._dt.timestamp())
