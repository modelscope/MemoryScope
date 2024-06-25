from abc import ABCMeta, abstractmethod
from typing import Dict, List

from models.base_model import BaseModel


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
        pass

    @abstractmethod
    async def async_retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        """
        :param text:
        :param limit_size:
        :param filter_dict:
        :return:
        """
        pass

    @abstractmethod
    def insert(self, node: MemoryNode):
        """ TODO 是否overwrite
        :return:
        """
        pass

    @abstractmethod
    def insert_batch(self):
        """
        :return:
        """
        pass

    @abstractmethod
    def delete(self):
        """
        :return:
        """
        pass

    @abstractmethod
    def flush(self):
        """
        :return:
        """
        pass
