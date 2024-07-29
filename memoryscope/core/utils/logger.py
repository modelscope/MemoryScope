import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(module)s:%(lineno)d] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOGGER_DICT = {}


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

    def _add_file_handler(self):
        """
        Adds a file handler to the logger which logs messages to a rotating file.

        The file is stored in a specified directory with a name derived from the logger's name and type.
        The file handler is set up to rotate when it reaches a certain size and keeps a defined number of backups.

        This method ensures the directory exists before creating the file handler and sets the formatter
        for consistent log message formatting.
        """
        file_path = Path().joinpath(self.dir_path, f"{self.name}.{self.file_type}")
        file_path.parent.mkdir(exist_ok=True)  # Ensure the directory exists
        file_name = file_path.as_posix()  # Get the absolute path as a string

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
            extra["trace_id"] = self.trace_id  # ⭐ Include trace_id from the logger in the log record extra data
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
            LOGGER_DICT[name] = Logger(name=name, **kwargs)

        return LOGGER_DICT[name]
