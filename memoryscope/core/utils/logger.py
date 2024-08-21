import os
import logging
import pprint
from logging.handlers import RotatingFileHandler
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

LOG_FORMAT = "%(asctime)s %(levelname)s [%(module)s:%(lineno)d] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOGGER_DICT = {}

def rich2text(rich_table):
    console = Console(width=150)
    with console.capture() as capture:
        console.print(rich_table)
    return '\n' + str(Text.from_ansi(capture.get()))

def append_memoryscope_uuid(dir_path):
    from memoryscope.core.memoryscope_context import get_memoryscope_uuid # pylint: disable=import-outside-toplevel
    dir_path = os.path.join(dir_path, get_memoryscope_uuid())
    return dir_path

class Logger(logging.Logger):
    """
    The `Logger` class handle the stream of information or errors in activities.
    """

    def __init__(self,
                 name: str,
                 level: int = logging.INFO,
                 format_style: str = LOG_FORMAT,
                 date_format_style: str = DATE_FORMAT,
                 to_stream: bool = False,
                 to_file: bool = True,
                 file_mode: str = "w",
                 file_type: str = "log",
                 dir_path: str = "log",
                 max_bytes: int = 1024 * 1024 * 1024,
                 backup_count: int = 10):
        """
        Initializes the Logger instance, setting up handlers for console and file logging based on provided parameters.

        Args:
            name (str): Identifier for the logger.
            level (int, optional): Logging level. Defaults to logging.INFO.
            format_style (str, optional): Log message format. Defaults to LOG_FORMAT constant.
            date_format_style (str, optional): Date format for logs. Defaults to DATE_FORMAT constant.
            to_stream (bool, optional): Enables console logging. Defaults to True.
            to_file (bool, optional): Enables file logging. Defaults to True.
            file_mode (str, optional): File open mode. Defaults to 'w'.
            file_type (str, optional): Log file extension type. Defaults to 'log'.
            dir_path (str, optional): Directory for log files. Defaults to 'log'.
            max_bytes (int, optional): Maximum log file size before rotation. Defaults to 1GB.
            backup_count (int, optional): Number of rotated log files to retain. Defaults to 10.
        """
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
            self._add_stream_handler()  # Adds a handler to output logs to the console
        if self.to_file:
            self._add_file_handler()  # Adds a handler to output logs to a file

        self.info(f"logger={name} is inited.")  # Logs an initialization message

    def log_dictionary_info(self, dictionary, title=""):
        self.info(self.format_current_context(dictionary, title))

    def format_current_context(self, context, title=""):
        pp = pprint.PrettyPrinter()
        pretty_string = pp.pformat(context)
        if title:
            pretty_string = f"{title}\n{pretty_string}"
        return self.wrap_in_box(pretty_string)

    def wrap_in_box(self, context):
        return rich2text(Panel(context, width=128))

    def format_chat_message(self, message):
        buf = []
        buf.append('\n')
        buf.append(f"LM Input:\n")
        for chat_message in message.meta_data['data']['messages']:
            buf.append(chat_message.content)
            buf.append('\n')
        buf.append(f"------------------------------------------\n")
        buf.append(f"LM Output:\n")
        buf.append(message.message.content)
        buf.append('\n')
        buf.append('\n')
        return self.wrap_in_box(''.join(buf))

    def format_rank_message(self, model_response):
        buf = []
        buf.append('\n')
        buf.append(f"Query Input:\n")
        buf.append(model_response.meta_data['data']['query_str'])
        buf.append('\n')
        buf.append(f"------------------------------------------\n")
        buf.append(f"Rank:\n")
        rank = 0
        for index, score in model_response.rank_scores.items():
            rank += 1
            node = model_response.meta_data['data']['nodes'][index]
            node_text = node.text
            buf.append(f"Score {score} | Rank {rank} | {node_text}\n")
        buf.append('\n')
        buf.append('\n')
        return self.wrap_in_box(''.join(buf))

    def _add_file_handler(self):
        """
        Adds a file handler to the logger which logs messages to a rotating file.

        The file is stored in a specified directory with a name derived from the logger's name and type.
        The file handler is set up to rotate when it reaches a certain size and keeps a defined number of backups.

        This method ensures the directory exists before creating the file handler and sets the formatter
        for consistent log message formatting.
        """
        file_path = Path().joinpath(self.dir_path, f"{self.name}.{self.file_type}")
        os.makedirs(file_path.parent, exist_ok=True)  # Ensure the directory exists
        file_name = file_path.as_posix()  # Get the absolute path as a string
        if not hasattr(Logger, 'notice_print'):
            Console().print(f"\nRegistering loggers at: {os.path.abspath(os.path.dirname(file_name))}. System logs can be found in this directory.\n", style="bold red")
            Logger.notice_print = True
        # Instantiate a rotating file handler with specified parameters
        file_handler = RotatingFileHandler(
            filename=file_name,
            maxBytes=self.max_bytes,  # Maximum size of the log file before rotation
            backupCount=self.backup_count,  # Number of backup files to keep
            encoding="utf-8")  # Set the encoding to UTF-8
        file_handler.setFormatter(self.formatter)  # Apply the logger's formatter to the handler
        self.addHandler(file_handler)  # Add the file handler to this logger instance

    def _add_stream_handler(self):
        """
        Adds a stream handler to the logger for console output. The handler is configured
        with the logger's formatter and set to use UTF-8 encoding.
        """
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(self.formatter)  # Configure the handler with the logger's formatter
        stream_handler.encoding = 'utf-8'  # Set the handler's encoding to UTF-8
        self.addHandler(stream_handler)  # Add the handler to the logger

    def close(self):
        """
        Closes all handlers associated with this logger instance.

        This method iterates over the handlers attached to the logger and
        calls their `close` method to ensure that any system resources used
        by the handlers are freed properly.
        """
        for handler in self.handlers:
            # Close each handler to release resources
            handler.close()

    def clear(self):
        """
        Clears all handlers from the logger.
        """
        self.handlers.clear()

    def set_trace_id(self, trace_id: str):
        """
        Sets the trace ID for the logger. If the provided trace ID is longer than 8 characters,
        it will be truncated to the first 8 characters.

        Args:
            trace_id (str): The trace identifier to be associated with the logs.
        """
        self.trace_id: str = trace_id
        if len(self.trace_id) >= 8:
            self.trace_id = self.trace_id[:8]

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        """
        Creates a log record with additional trace_id included in the extra information.

        This method extends the default behavior of creating a log record by adding
        a trace_id from the logger instance to the record's extra data, allowing
        for traceability within logged data.

        Args:
            name (str): The name of the logger.
            level (int): The logging level of the record.
            fn (str): The name of the function containing the logging call.
            lno (int): The line number at which the logging call was made.
            msg (str): The logged message, before formatting.
            args (tuple): The arguments to the log message.
            exc_info (tuple): Exception information or None.
            func (function): The function where the logging call was made. Defaults to None.
            extra (dict): Additional information for the log record. Defaults to None.
            sinfo (str): Stack trace information or None.

        Returns:
            logging.LogRecord: The created log record with potentially enriched 'extra' field.
        """
        if extra is None:
            extra = {}
        if self.trace_id:
            extra["trace_id"] = self.trace_id  # Include trace_id from the logger in the log record extra data
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)

    @classmethod
    def get_logger(cls, name: str = None, **kwargs):
        """
        Retrieves or creates a logger instance with the specified name and configurations.

        If no name is provided, it defaults to the first registered logger's name or 'default' if none exist.
        This method ensures that only one logger instance exists per name by reusing existing instances
        stored in `LOGGER_DICT`.

        Args:
            name (str, optional): The name of the logger. Defaults to None, which triggers auto-naming logic.
            **kwargs: Additional keyword arguments to configure the logger.

        Returns:
            Logger: The requested or newly created logger instance.
        """
        if name is None:
            if LOGGER_DICT:
                name = list(LOGGER_DICT.keys())[0]
            else:
                name = "default"

        if name not in LOGGER_DICT:
            logger_dir = kwargs.get('dir_path', 'log')
            logger_dir = append_memoryscope_uuid(logger_dir)
            LOGGER_DICT[name] = Logger(name=name, dir_path=logger_dir, **kwargs)

        return LOGGER_DICT[name]
