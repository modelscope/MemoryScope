import re

from utils.logger import Logger


class ResponseTextParser(object):
    pattern_v1 = re.compile(r"<(.*?)>")

    def __init__(self, response_text: str):
        self.response_text: str = response_text.strip()
        self.logger: Logger = Logger.get_logger()

    def parse_v1(self, prefix: str = ""):
        result = []
        for line in self.response_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            matches = [match.group(1) for match in self.pattern_v1.finditer(line)]
            if matches:
                result.append(matches)
        self.logger.info(
            f"{prefix} response_text={self.response_text} result={result}", stacklevel=2
        )
        return result

    def parse_v2(self, prefix: str = ""):
        result = []
        for line in self.response_text.split("\n"):
            line = line.strip()
            if not line or line == "无":
                continue
            result.append(line)
        self.logger.info(
            f"{prefix} response_text={self.response_text} result={result}", stacklevel=2
        )
        return result
