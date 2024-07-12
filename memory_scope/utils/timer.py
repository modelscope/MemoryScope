import time

from memory_scope.utils.logger import Logger


class Timer(object):
    """
    A class used to measure the execution time of code blocks. It supports logging the elapsed time and can be customized
    to display time in seconds or milliseconds.
    """

    def __init__(self, name: str, log_time: bool = True, use_ms: bool = True, **kwargs):
        """
        Initializes the Timer object with a name, logging preference, time unit preference, and additional keyword arguments.

        Args:
            name (str): The name associated with this timer instance, often used in logs.
            log_time (bool, optional): Determines if the elapsed time should be logged. Defaults to True.
            use_ms (bool, optional): Specifies whether to use milliseconds as the time unit in logs. Defaults to True.
            **kwargs: Additional keyword arguments that might be utilized by the logger or other components.
        """
        self.name: str = name
        self.log_time: bool = log_time
        self.use_ms: bool = use_ms
        self.kwargs: dict = kwargs

        self.logger = Logger.get_logger()

        # time record
        self.t_start = 0
        self.t_end = 0
        self.cost = 0

    @classmethod
    def kwargs_to_str(cls, float_precision: int = 4, **kwargs):
        """
        Converts keyword arguments into a formatted string, with floats controlled by a precision setting.

        Args:
            float_precision (int, optional): The number of decimal places for floating point numbers. Defaults to 4.
            **kwargs: Arbitrary keyword arguments to be converted into strings.

        Returns:
            str: A single string composed of the keyword arguments and their values, separated by spaces.
        """
        line_list = []
        for k, v in kwargs.items():
            if isinstance(v, float):
                float_style = f".{float_precision}f"
                line = f"{k}={v:{float_style}}"  # Format float value with specified precision
            else:
                line = f"{k}={v}"  # Keep other types as is
            line_list.append(line)

        return " ".join(line_list)  # Join all parts into a single string with spaces

    def __enter__(self):
        self.t_start = time.time()
        # with Timer("XXX") as t, need return self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Records the end time of the timed code block and calculates the elapsed time.
        Logs the time cost if logging is enabled, with optional message customization.

        Args:
            exc_type: The exception type (unused).
            exc_val: The exception value (unused).
            exc_tb: The traceback (unused).
        """
        self.t_end = time.time()
        self.cost = self.t_end - self.t_start
        if self.use_ms:
            self.cost *= 1000

        if self.log_time:
            line = f"{self.name}.timer"

            if self.use_ms:
                line = f"{line} cost={self.cost:.1f}ms"
            else:
                line = f"{line} cost={self.cost:.4f}s"

            if self.kwargs:
                line = f"{line} {self.kwargs_to_str(**self.kwargs)}"

            self.logger.info(line, stacklevel=3)

    @property
    def cost_str(self):
        """
        Returns a string representation of the time cost, formatted as seconds or milliseconds
        based on the `use_ms` attribute.

        Returns:
            A string indicating the time cost in the chosen unit (seconds or milliseconds).
        """
        if self.use_ms:
            return f"{self.cost:.1f}ms"
        else:
            return f"{self.cost:.4f}s"


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
