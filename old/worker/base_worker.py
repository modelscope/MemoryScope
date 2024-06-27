from typing import Any, Dict

from ..utils.logger import Logger
from ..utils.timer import Timer


class BaseWorker(object):

    def __init__(self, raise_exception: bool = True, **kwargs):
        super(BaseWorker, self).__init__(**kwargs)
        # 异常是否继续执行
        self.raise_exception: bool = raise_exception

        # True 为正常运行，False会结束整个pipeline
        self.continue_run: bool = True

        # 短name
        self._name_simple: str = ""

        # 是否多线程环境
        self.is_multi_thread: bool = False

        # pipeline 上下文
        self.context_dict: Dict[str, Any] | None = None
        self.context_lock = None

        # 日志
        self.logger: Logger = Logger.get_logger()

        # worker 参数
        self.kwargs: dict = kwargs

    def _run(self):
        raise NotImplementedError

    def run(self):
        self.logger.info(f"----- Begin {self.name_simple} -----")
        with Timer(self.name_simple, log_time=False) as t:
            if self.raise_exception:
                self._run()
            else:
                try:
                    self._run()
                except Exception as e:
                    self.logger.exception(f"run {self.name_simple} failed! args={e.args}")

            self.logger.info(f"----- End {self.name_simple} cost={t.cost_str}-----")

    def set_context_dict(self, context_dict: dict, context_lock=None):
        self.context_dict = context_dict
        if context_lock is not None:
            self.context_lock = context_lock
            self.is_multi_thread = True

    def get_context(self, key: str, default=None):
        return self.context_dict.get(key, default)

    def set_context(self, key: str, value: Any):
        if self.is_multi_thread:
            # add lock to multi thread
            with self.context_lock:
                self.context_dict[key] = value
        else:
            self.context_dict[key] = value

    def __getattr__(self, key):
        return self.kwargs[key]

    @property
    def name_simple(self) -> str:
        if not self._name_simple:
            self._name_simple = self.__class__.__name__.replace("Worker", "")
        return self._name_simple