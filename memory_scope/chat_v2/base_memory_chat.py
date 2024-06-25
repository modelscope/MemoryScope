from abc import ABCMeta, abstractmethod


class BaseMemoryChat(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        self.kwargs = kwargs


    @abstractmethod
    def chat_with_memory(self, query: str):
        """
        :param query:
        :return:
        """

    def run(self):
        pass
