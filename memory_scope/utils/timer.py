import time

from memory_scope.utils.logger import Logger


class Timer(object):

    def __init__(self, name: str, log_time: bool = True, use_ms: bool = False, **kwargs):
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
        line_list = []
        for k, v in kwargs.items():
            if isinstance(v, float):
                float_style = f".{float_precision}f"
                line = f"{k}={v:{float_style}}"
            else:
                line = f"{k}={v}"
            line_list.append(line)

        return " ".join(line_list)

    def __enter__(self):
        self.t_start = time.time()
        # with Timer("XXX") as t, need return self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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
        if self.use_ms:
            return f"{self.cost:.1f}ms"
        else:
            return f"{self.cost:.4f}s"


def timer(func):
    def wrapper(*args, **kwargs):
        with Timer(name=func.__name__, **kwargs):
            return func(*args, **kwargs)

    return wrapper
