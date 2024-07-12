from abc import ABCMeta, abstractmethod
from typing import Dict, List

from memory_scope.scheme.memory_node import MemoryNode


class BaseMemoryStore(metaclass=ABCMeta):
    """
    An abstract base class defining the interface for a memory store which handles memory nodes.
    It outlines essential operations like retrieval, updating, flushing, and closing of memory scopes.
    """

    @abstractmethod
    def retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    @abstractmethod
    def update_memories(self, nodes: MemoryNode | List[MemoryNode]):
        """
        Updates the memories based on their status:
        - New: Embeds and inserts the memory node.
        - Modified: Directly updates the memory node.
        - Content Modified: Embeds and then updates the memory node.
        - Active: No action required.
        - Expired: Updates the memory node.

        Args:
            nodes (MemoryNode | List[MemoryNode]): A single memory node or a list of memory nodes to be updated.
        """
        pass

    def flush(self):
        """
        Flushes any pending memory updates or operations to ensure data consistency.
        This method should be overridden by subclasses to provide the specific flushing mechanism.
        """
        pass

    @abstractmethod
    def close(self):
        """
        Closes the memory store, releasing any resources associated with it.
        Subclasses must implement this method to define how the memory store is properly closed.
        """
        pass
