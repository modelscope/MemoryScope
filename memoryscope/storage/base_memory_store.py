from abc import ABCMeta, abstractmethod
from typing import Dict, List

from memoryscope.scheme.memory_node import MemoryNode


class BaseMemoryStore(metaclass=ABCMeta):
    """
    An abstract base class defining the interface for a memory store which handles memory nodes.
    It outlines essential operations like retrieval, updating, flushing, and closing of memory scopes.
    """

    @abstractmethod
    def retrieve_memories(self,
                          query: str = "",
                          top_k: int = 3,
                          filter_dict: Dict[str, List[str]] = None) -> List[MemoryNode]:
        """
        Retrieves a list of MemoryNode objects that are most relevant to the query,
        considering a filter dictionary for additional constraints. The number of nodes returned
        is limited by top_k.

        Args:
            query (str): The query string used to find relevant memories.
            top_k (int): The maximum number of MemoryNode objects to return.
            filter_dict (Dict[str, List[str]]): A dictionary with keys representing filter fields
                                                and values as lists of strings for filtering criteria.

        Returns:
            List[MemoryNode]: A list of MemoryNode objects sorted by relevance to the query,
                              limited to top_k items.
        """
        pass

    @abstractmethod
    async def a_retrieve_memories(self,
                                  query: str = "",
                                  top_k: int = 3,
                                  filter_dict: Dict[str, List[str]] = None) -> List[MemoryNode]:
        """
        Asynchronously retrieves a list of MemoryNode objects that best match the query,
        respecting a filter dictionary, with the result size capped at top_k.

        Args:
            query (str): The text to search for in memory nodes.
            top_k (int): Maximum number of nodes to return.
            filter_dict (Dict[str, List[str]]): Filters to apply on memory nodes.

        Returns:
            List[MemoryNode]: A list of up to top_k MemoryNode objects matching the criteria.
        """
        pass

    @abstractmethod
    def batch_insert(self, nodes: List[MemoryNode]):
        pass

    @abstractmethod
    def batch_update(self, nodes: List[MemoryNode], update_embedding: bool = True):
        pass

    @abstractmethod
    def batch_delete(self, nodes: List[MemoryNode]):
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
