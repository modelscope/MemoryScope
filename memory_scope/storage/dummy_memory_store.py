from typing import Dict, List

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_memory_store import BaseMemoryStore


class DummyMemoryStore(BaseMemoryStore):
    """
    Placeholder implementation of a memory storage system interface. Defines methods for querying, updating,
    and closing memory nodes with asynchronous capabilities, leveraging an embedding model for potential
    semantic retrieval. Actual storage operations are not implemented.
    """

    def __init__(self, embedding_model: BaseModel, **kwargs):
        """
        Initializes the DummyMemoryStore with an embedding model and additional keyword arguments.

        Args:
            embedding_model (BaseModel): The model used to embed data for potential similarity-based retrieval.
            **kwargs: Additional keyword arguments for configuration or future expansion.
        """
        self.embedding_model: BaseModel = embedding_model
        self.kwargs = kwargs

    def retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
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

    async def a_retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
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

    def update_memories(self, nodes: MemoryNode | List[MemoryNode]):
        """
        Updates the stored memories with a single MemoryNode or a list of MemoryNode objects.

        Args:
            nodes (MemoryNode | List[MemoryNode]): A single MemoryNode or a collection of MemoryNode objects 
                                                   to be updated in the memory store.
        """
        pass

    def close(self):
        """
        Closes the memory store, releasing any resources it holds. This method should be called 
        when the memory store is no longer needed.
        """
        pass
