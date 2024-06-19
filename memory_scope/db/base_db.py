from abc import ABCMeta, abstractmethod

from memory_scope.models.base_model import BaseModel


class BaseDBClient(metaclass=ABCMeta):

    def __init__(self, index_name: str, embedding_model: BaseModel, content_key: str = "text", **kwargs):
        self.index_name: str = index_name
        self.embedding_model: BaseModel = embedding_model
        self.content_key: str = content_key
        self.kwargs: dict = kwargs

    @abstractmethod
    def retrieve(self, text: str, limit_size: int):
        """
        :param text:
        :param limit_size:
        :return:
        """

    @abstractmethod
    def insert(self, text: str):
        """ TODO 是否overwrite
        :return:
        """

    @abstractmethod
    def insert_batch(self):
        """
        :return:
        """

    @abstractmethod
    def delete(self):
        """
        :return:
        """