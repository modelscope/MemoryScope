import threading
from abc import ABCMeta, abstractmethod
from typing import List, Dict

from memory_scope.memory.operation.base_operation import BaseOperation
from memory_scope.scheme.message import Message
from memory_scope.utils.logger import Logger


class BaseMemoryService(metaclass=ABCMeta):
    def __init__(self, read_memory_key: str = "read_memory", **kwargs):
        self.read_memory_key: str = read_memory_key

        self._operation_dict: Dict[str, BaseOperation] = {}
        self._op_description_dict: Dict[str, str] = {}

        self.chat_messages: List[Message] = []
        self.message_lock = threading.Lock

        self.logger = Logger.get_logger()
        self.kwargs = kwargs

    def add_messages(self, messages: List[Message] | Message):
        pass

    def prepare_service(self):
        pass

    @abstractmethod
    def operate(self, op_name: str):
        raise NotImplementedError

    @property
    def op_description_dict(self) -> Dict[str, str]:
        if not self._op_description_dict:
            self._op_description_dict = {k: v.description for k, v in self._operation_dict.items()}
        return self._op_description_dict

    def read_memory(self):
        assert self.read_memory_key in self._operation_dict, f"op={self.read_memory_key} is not inited!"
        return self.operate(self.read_memory_key)
