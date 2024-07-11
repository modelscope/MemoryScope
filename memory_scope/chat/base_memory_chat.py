from abc import ABCMeta, abstractmethod

from memory_scope.memory.service.base_memory_service import BaseMemoryService


class BaseMemoryChat(metaclass=ABCMeta):

    @abstractmethod
    def chat_with_memory(self, query: str):
        """
        :param query:
        :return:
        """

    @property
    def memory_service(self) -> BaseMemoryService:
        raise NotImplementedError

    def run(self):
        pass
