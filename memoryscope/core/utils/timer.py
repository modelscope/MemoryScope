import time
from typing import Literal

from memoryscope.core.utils.logger import Logger

TIME_LOG_TYPE = Literal["end", "wrap", "none"]


class Timer(object):
    """
    A class used to measure the execution time of code blocks. It supports logging the elapsed time and can be
    customized to display time in seconds or milliseconds.
    """

    def __init__(self,
                 name: str,
                 time_log_type: TIME_LOG_TYPE = "end",
                 use_ms: bool = True,
                 stack_level: int = 2,
                 float_precision: int = 4,
                 **kwargs):

        """
        Initializes the `Timer` instance with the provided args and sets up a logger

        Args:
            name (str): The log name.
            time_log_type (str): The log type. Defaults to 'End'.
            use_ms (bool): Use 'ms' as the timescale or not. Defaults to True.
            stack_level (int): The stack level of log. Defaults to 2.
            float_precision (int): The precision of cost time. Defaults to 4.

        """

        self.name: str = name
        self.time_log_type: TIME_LOG_TYPE = time_log_type
        self.use_ms: bool = use_ms
        self.stack_level: int = stack_level
        self.float_precision: int = float_precision
        self.kwargs: dict = kwargs

        # time recorder
        self.t_start = 0
        self.t_end = 0
        self.cost = 0

        self.logger = Logger.get_logger()

    def _set_cost(self):
        """
        Accumulate the cost time.
        """
        self.t_end = time.time()
        self.cost = self.t_end - self.t_start
        if self.use_ms:
            self.cost *= 1000

    @property
    def cost_str(self):
        """
        Represent the cost time into a formatted string.
        """
        self._set_cost()
        if self.use_ms:
            return f"cost={self.cost:.4f}ms"
        else:
            return f"cost={self.cost:.4f}s"

    def __enter__(self, *args, **kwargs):
        """
        Begin timing.
        """
        self.t_start = time.time()
        if self.time_log_type == "wrap":
            self.logger.info(f"----- {self.name}.begin -----")
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """
        End timing and print the formatted log.
        """
        if self.time_log_type == "none":
            return

        lines = []
        if self.time_log_type == "wrap":
            lines.append(f"----- {self.name}.end -----")
        else:
            lines.append(self.name)

        lines.append(self.cost_str)

        if self.kwargs:
            for k, v in self.kwargs.items():
                if isinstance(v, float):
                    float_style = f".{self.float_precision}f"
                    line = f"{k}={v:{float_style}}"
                else:
                    line = f"{k}={v}"
                lines.append(line)

        self.logger.info(" ".join(lines), stacklevel=self.stack_level)


def timer(func):
    """
    A decorator function that measures the execution time of the wrapped function.

    Args:
        func (Callable): The function to be wrapped and timed.

    Returns:
        Callable: The wrapper function that includes timing functionality.
    """

    def wrapper(*args, **kwargs):
        """
        The wrapper function that manages the timing of the original function.

        Args:
            *args: Variable length argument list for the decorated function.
            **kwargs: Arbitrary keyword arguments for the decorated function.

        Returns:
            Any: The result of the decorated function.
        """
        with Timer(name=func.__name__, **kwargs):
            return func(*args, **kwargs)

    return wrapper
