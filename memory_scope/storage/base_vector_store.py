from abc import ABCMeta, abstractmethod
from typing import Dict, List

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode


class BaseVectorStore(metaclass=ABCMeta):

    def __init__(self, index_name: str, embedding_model: BaseModel, content_key: str = "text", **kwargs):
        self.index_name: str = index_name
        self.embedding_model: BaseModel = embedding_model
        self.content_key: str = content_key
        self.kwargs: dict = kwargs

    @abstractmethod
    def retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        """
        :param text:
        :param limit_size:
        :param filter_dict:
        :return:
        """

    @abstractmethod
    async def async_retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        """
        :param text:
        :param limit_size:
        :param filter_dict:
        :return:
        """

    @abstractmethod
    def insert(self, node: MemoryNode):
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

    @abstractmethod
    def flush(self):
        """
        :return:
        """
