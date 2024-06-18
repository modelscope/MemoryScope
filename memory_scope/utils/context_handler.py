import os
import threading
from typing import Dict, Any

from utils.logger import Logger

class ContextHandler(object):
    def __init__(self):
        # 上下文 所有worker共享
        self.context_dict: Dict[str, Any] = {}

        # 日志
        self.logger = Logger.get_logger()

        # 全局锁
        self.context_lock = threading.Lock()

    def flush(self):
        self.context_dict: Dict[str, Any] = {}

    def get_context(self, key: str, default=None):
        # 多线程环境下，如果是指针下修改，不安全
        return self.context_dict.get(key, default)

    def set_context(self, key: str, value: Any, is_multi_thread: bool = False):
        if is_multi_thread:
            # add lock to multi thread
            with self.context_lock:
                self.context_dict[key] = value
        else:
            self.context_dict[key] = value
