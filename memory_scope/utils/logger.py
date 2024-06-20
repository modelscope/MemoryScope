import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(trace_id)s %(module)s:%(lineno)d] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOGGER_DICT = {}


class Logger(logging.Logger):
    def __init__(self,
                 name: str,
                 level: int = logging.INFO,
                 format_style: str = LOG_FORMAT,
                 date_format_style: str = DATE_FORMAT,
                 to_stream: bool = True,
                 to_file: bool = True,
                 file_mode: str = "w",
                 file_type: str = "log",
                 dir_path: str = "log",
                 max_bytes: int = 1024 * 1024 * 1024,
                 backup_count: int = 10):
        super(Logger, self).__init__(name, level)

        self.formatter = logging.Formatter(format_style, date_format_style)
        self.date_format_style = date_format_style
        self.to_stream: bool = to_stream
        self.to_file: bool = to_file
        self.file_mode: str = file_mode
        self.file_type: str = file_type
        self.dir_path: str = dir_path

        self.max_bytes: int = max_bytes
        self.backup_count: int = backup_count

        self.trace_id: str = ""

        if self.to_stream:
            self._add_stream_handler()
        if self.to_file:
            self._add_file_handler()

        self.info(f"logger={name} is inited.")

    def _add_file_handler(self):
        file_path = Path().joinpath(self.dir_path, f"{self.name}.{self.file_type}")
        file_path.parent.mkdir(exist_ok=True)
        file_name = file_path.as_posix()

        file_handler = RotatingFileHandler(
            filename=file_name,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8")
        file_handler.setFormatter(self.formatter)
        self.addHandler(file_handler)

    def _add_stream_handler(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(self.formatter)
        stream_handler.encoding = 'utf-8'
        self.addHandler(stream_handler)

    def close(self):
        for handler in self.handlers:
            handler.close()

    def clear(self):
        self.handlers.clear()

    def set_trace_id(self, trace_id: str):
        self.trace_id: str = trace_id
        if len(self.trace_id) >= 8:
            self.trace_id = self.trace_id[:8]

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        if extra is None:
            extra = {}
        extra["trace_id"] = self.trace_id
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)

    @classmethod
    def get_logger(cls, name: str = None, **kwargs):
        if name is None:
            if LOGGER_DICT:
                name = list(LOGGER_DICT.keys())[0]
            else:
                name = "default"

        if name not in LOGGER_DICT:
            LOGGER_DICT[name] = Logger(name=name, **kwargs)

        return LOGGER_DICT[name]
