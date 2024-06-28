from abc import ABCMeta, abstractmethod
from typing import Dict, List

from memory_scope.scheme.memory_node import MemoryNode


class BaseVectorStore(metaclass=ABCMeta):

    @abstractmethod
    def retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        pass

    @abstractmethod
    async def async_retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        pass

    @abstractmethod
    def insert(self, node: MemoryNode):
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
