import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List

from common.context_handler import ContextHandler
from common.logger import Logger
from common.timer import Timer


class BaseWorker(object):

    def __init__(self,
                 context_handler: ContextHandler,
                 is_multi_thread: bool = False,
                 thread_pool: ThreadPoolExecutor = None,
                 raise_exception: bool = True,
                 logger: Logger = None,
                 **kwargs):
        super(BaseWorker, self).__init__(**kwargs)

        # 原始参数
        self.context_handler: ContextHandler = context_handler
        self.is_multi_thread: bool = is_multi_thread
        self.thread_pool: ThreadPoolExecutor = thread_pool
        self.raise_exception: bool = raise_exception
        self.logger: Logger = logger

        # 日志
        if not self.logger:
            self.logger: Logger = Logger.get_logger()
        self.logger.debug(f"init {self.__class__.__name__} is_multi_thread={is_multi_thread}")

        # 提交的线程池
        self.thread_list: list = []

        # True 为正常运行，False会结束整个pipeline
        self.continue_run: bool = True

        # 运行信息，保存到ext_info
        self.run_infos: List[str] = []

        # 运行时间
        self.run_cost: float = 0

        # 短name
        self._name_simple: str = ""

    def _run(self):
        pass

    def submit_thread(self, fn, /, *args, sleep_time: float = 0, **kwargs):
        if self.thread_list:
            time.sleep(sleep_time)
        t = self.thread_pool.submit(fn, *args, **kwargs)
        self.thread_list.append(t)
        return t

    def join_threads(self):
        result_list = []
        for future in as_completed(self.thread_list):
            result_list.append(future.result())
        self.thread_list.clear()
        return result_list

    def run(self):
        self.logger.info(f"----- Begin {self.name_simple} -----")
        with Timer(self.name_simple, log_time=False) as t:
            if self.raise_exception:
                self._run()
            else:
                try:
                    self._run()
                except Exception as e:
                    self.add_run_info(f"run {self.name_simple} failed! args={e.args}")

        self.run_cost = t.cost
        self.logger.info(f"----- End {self.name_simple} {t.get_cost_info()}-----")

    def get_context(self, key: str, default=None):
        return self.context_handler.get_context(key, default)

    def set_context(self, key: str, value: Any):
        self.context_handler.set_context(key, value, self.is_multi_thread)

    def get_param(self, key: str, default=None):
        return self.context_handler.env_configs.get(key, default)

    @property
    def env_type(self) -> str:
        return self.context_handler.env_type.value

    @property
    def scene(self) -> str:
        return self.context_handler.scene

    @property
    def method(self) -> str:
        return self.context_handler.method

    @property
    def algo_version(self) -> str:
        return self.context_handler.algo_version

    @property
    def name_simple(self) -> str:
        if not self._name_simple:
            self._name_simple = self.__class__.__name__.replace("Worker", "")
        return self._name_simple

    def add_run_info(self, msg: str, log_warning: bool = True, continue_run: bool = True):
        if not continue_run:
            self.continue_run = False
            msg = f"{msg} pipeline is ended by {self.name_simple}!"

        if log_warning:
            self.logger.warning(msg, stacklevel=2)

        self.run_infos.append(msg)

    @property
    def run_info_dict(self):
        return {
            "name": self.name_simple,
            "cost": self.run_cost,
            "info": self.run_infos,
        }
