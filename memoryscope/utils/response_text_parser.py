import re
from typing import List

from memoryscope.constants.language_constants import NONE_WORD
from memoryscope.utils.global_context import G_CONTEXT
from memoryscope.utils.logger import Logger


class ResponseTextParser(object):
    """
    The `ResponseTextParser` class is designed to parse and process response texts. It provides methods to extract specific
    patterns from the text and filter out unnecessary information, while also logging the processing steps and outcomes.
    """

    pattern_v1 = re.compile(r"<(.*?)>")  # Regular expression pattern to match content within angle brackets

    def __init__(self, response_text: str):
        """
        Initializes the `ResponseTextParser` instance with the provided response text and sets up a logger.

        Args:
            response_text (str): The raw response text that needs to be parsed and processed.
        """
        self.response_text: str = response_text.strip()  # Strips leading and trailing whitespace from the response text
        self.logger: Logger = Logger.get_logger()  # Initializes a logger instance for logging parsing activities

    def parse_v1(self, prefix: str = "") -> List[str]:
        """
        Extract specific patterns from the text which match content within angle brackets.

        Args:
            prefix (str): The prefix of log. Defaults to "".
        
        Returns:
            Contents match the specific patterns.
        """
        result = []
        for line in self.response_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            matches = [match.group(1) for match in self.pattern_v1.finditer(line)]
            if matches:
                result.append(matches)
        self.logger.info(f"{prefix} response_text={self.response_text} result={result}", stacklevel=2)
        return result

    def parse_v2(self, prefix: str = "") -> List[str]:
        """
        Extract lines which contain NONE_WORD in Chinese or English.

        Args:
            prefix (str): The prefix of log. Defaults to "".
        
        Returns:
            Contents match the specific patterns.
        """
        result = []
        for line in self.response_text.split("\n"):
            line = line.strip()
            if not line or line.lower() == NONE_WORD.get(G_CONTEXT.language):
                continue
            result.append(line)
        self.logger.info(f"{prefix} response_text={self.response_text} result={result}", stacklevel=2)
        return result
