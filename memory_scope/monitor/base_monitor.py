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
        """ TODO @xianzhe
        :return:
        """

    @abstractmethod
    def flush(self):
        """
        :return:
        """
