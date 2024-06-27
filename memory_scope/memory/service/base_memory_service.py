import threading
from abc import ABCMeta, abstractmethod
from typing import List, Dict

from memory_scope.memory.operation.base_operation import BaseOperation
from memory_scope.scheme.message import Message
from memory_scope.utils.logger import Logger


class BaseMemoryService(metaclass=ABCMeta):
    def __init__(self,
                 memory_operations: Dict[str, dict],
                 read_memory_key: str = "read_memory",
                 **kwargs):
        self.memory_operations: Dict[str, dict] = memory_operations
        self.read_memory_key: str = read_memory_key

        self._operation_dict: Dict[str, BaseOperation] = {}
        self._op_description_dict: Dict[str, str] = {}
        self.chat_messages: List[Message] = []
        self.message_lock = threading.Lock

        self.logger = Logger.get_logger()
        self.kwargs = kwargs

        self._init_operation(memory_operations)

    @abstractmethod
    def _init_operation(self, memory_operations: Dict[str, dict]):
        raise NotImplementedError

    @abstractmethod
    def add_messages(self, messages: List[Message] | Message):
        raise NotImplementedError

    def prepare_service(self):
        pass

    @abstractmethod
    def do_operation(self, op_name: str):
        raise NotImplementedError

    @property
    def op_description_dict(self) -> Dict[str, str]:
        if not self._op_description_dict:
            self._op_description_dict = {k: v.description for k, v in self._operation_dict.items()}
        return self._op_description_dict

    def read_memory(self):
        assert self.read_memory_key in self._operation_dict, f"op={self.read_memory_key} is not inited!"
        return self.do_operation(self.read_memory_key)
