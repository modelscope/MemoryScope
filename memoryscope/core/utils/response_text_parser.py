import re
from typing import List

from memoryscope.constants.language_constants import NONE_WORD
from memoryscope.core.utils.logger import Logger
from memoryscope.enumeration.language_enum import LanguageEnum


class ResponseTextParser(object):
    """
    The `ResponseTextParser` class is designed to parse and process response texts. It provides methods to extract
    patterns from the text and filter out unnecessary information, while also logging the processing steps and outcomes.
    """

    PATTERN_V1 = re.compile(r"<(.*?)>")  # Regular expression pattern to match content within angle brackets

    def __init__(self, response_text: str, language: LanguageEnum, logger_prefix: str = ""):
        # Strips leading and trailing whitespace from the response text
        self.response_text: str = response_text.strip()
        self.language: LanguageEnum = language

        # The prefix of log. Defaults to "".
        self.logger_prefix: str = logger_prefix

        # Initializes a logger instance for logging parsing activities
        self.logger: Logger = Logger.get_logger()

    def parse_v1(self) -> List[List[str]]:
        """
        Extract specific patterns from the text which match content within angle brackets.

        Returns:
            Contents match the specific patterns.
        """
        result = []
        for line in self.response_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            matches = [match.group(1) for match in self.PATTERN_V1.finditer(line)]
            if matches:
                result.append(matches)
        self.logger.info(f"{self.logger_prefix} response_text={self.response_text} result={result}", stacklevel=2)
        return result

    def parse_v2(self) -> List[str]:
        """
        Extract lines which contain NONE_WORD.

        Returns:
            Contents match the specific patterns.
        """
        result = []
        for line in self.response_text.split("\n"):
            line = line.strip()
            if not line or line.lower() == NONE_WORD.get(self.language):
                continue
            result.append(line)
        self.logger.info(f"{self.logger_prefix} response_text={self.response_text} result={result}", stacklevel=2)
        return result
