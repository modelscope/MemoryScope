from abc import ABCMeta, abstractmethod
from typing import List, Dict

from memory_scope.scheme.message import Message
from memory_scope.utils.logger import Logger


class BaseMemoryService(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        self.logger = Logger.get_logger()
        self.kwargs = kwargs

    def submit_messages(self, messages: List[Message] | Message):
        pass

    def prepare_service(self):
        pass

    @abstractmethod
    def do_operation(self, op_name: str):
        pass

    @abstractmethod
    def get_op_description_dict(self) -> Dict[str, str]:
        pass
