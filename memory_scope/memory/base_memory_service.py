from abc import ABCMeta


class BaseMemoryService(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
