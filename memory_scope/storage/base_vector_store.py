from abc import ABCMeta, abstractmethod
from typing import Dict, List

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode


class BaseVectorStore(metaclass=ABCMeta):

    def __init__(self,
                 index_name: str = "",
                 embedding_model: BaseModel | None = None,
                 **kwargs):
        self.index_name: str = index_name
        self.embedding_model: BaseModel = embedding_model
        self.kwargs: dict = kwargs

    @abstractmethod
    def retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        pass

    @abstractmethod
    async def async_retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        pass

    @abstractmethod
    def insert(self, node: MemoryNode):
        """ TODO 是否overwrite
        :return:
        """
        pass

    def insert_batch(self, nodes: List[MemoryNode]):
        pass

    def delete(self, node: MemoryNode):
        pass

    def update(self, node: MemoryNode):
        pass

    def flush(self):
        pass

    def close(self):
        pass
