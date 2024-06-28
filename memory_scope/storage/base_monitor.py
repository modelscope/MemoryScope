from abc import ABCMeta, abstractmethod


class BaseMonitor(metaclass=ABCMeta):

    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def add(self):
        """
        :return:
        """

    @abstractmethod
    def add_token(self):
        """
        :return:
        """

    def flush(self):
        pass

    def close(self):
        pass
