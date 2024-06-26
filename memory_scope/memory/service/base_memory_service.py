from abc import ABCMeta, abstractmethod

from memory_scope.utils.logger import Logger


class BaseMemoryService(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        self.logger = Logger.get_logger()
        self.kwargs = kwargs

    @abstractmethod
    def get_short_memory(self):
        pass
