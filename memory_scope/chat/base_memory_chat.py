from abc import ABCMeta, abstractmethod

from memory_scope.chat.memory_service import MemoryService


class BaseMemoryChat(metaclass=ABCMeta):

    def __init__(self, chat_name: str, memory_user_name: str, **kwargs):
        self.memory_service = MemoryService(chat_name=chat_name,
                                            memory_user_name=memory_user_name,
                                            **kwargs)

    @abstractmethod
    def chat_with_memory(self, query: str):
        """
        :param query:
        :return:
        """
