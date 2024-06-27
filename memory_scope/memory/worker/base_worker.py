from abc import ABCMeta, abstractmethod
from typing import Any, Dict

from memory_scope.utils.logger import Logger
from memory_scope.utils.timer import Timer


class BaseWorker(metaclass=ABCMeta):

    def __init__(self,
                 name: str,
                 context: Dict[str, Any],
                 context_lock=None,
                 raise_exception: bool = True,
                 is_multi_thread: bool = False,
                 **kwargs):

        self.name: str = name
        self.context: Dict[str, Any] = context
        self.context_lock = context_lock
        self.raise_exception: bool = raise_exception
        self.is_multi_thread: bool = is_multi_thread
        self.kwargs: dict = kwargs

        self.continue_run: bool = True
        self.logger: Logger = Logger.get_logger()

    @abstractmethod
    def _run(self):
        raise NotImplementedError

    def run(self):
        self.logger.info(f"----- worker_{self.name}_begin -----")
        with Timer(self.name, log_time=False) as t:
            if self.raise_exception:
                self._run()
            else:
                try:
                    self._run()
                except Exception as e:
                    self.logger.exception(f"run {self.name} failed! args={e.args}")

            self.logger.info(f"----- worker_{self.name}_end cost={t.cost_str}-----")

    def get_context(self, key: str, default=None):
        return self.context.get(key, default)

    def set_context(self, key: str, value: Any):
        if self.is_multi_thread:
            with self.context_lock:
                self.context_dict[key] = value
        else:
            self.context[key] = value

    def __getattr__(self, key):
        return self.kwargs[key]
