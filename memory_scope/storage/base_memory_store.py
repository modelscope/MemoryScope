from abc import ABCMeta, abstractmethod
from typing import Dict, List

from memory_scope.scheme.memory_node import MemoryNode


class BaseMemoryStore(metaclass=ABCMeta):

    @abstractmethod
    def retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    @abstractmethod
    def update_memories(self, nodes: MemoryNode | List[MemoryNode]):
        """
        status:
        1. new: emb & insert
        2. modified: update
        3. content_modified: emb & update
        4. active: do nothing
        5. expired: update
        """

    def flush(self):
        pass

    @abstractmethod
    def close(self):
        pass
