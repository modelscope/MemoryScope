from typing import Dict, List

from memoryscope.core.models.base_model import BaseModel
from memoryscope.core.storage.base_memory_store import BaseMemoryStore
from memoryscope.scheme.memory_node import MemoryNode


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

    def retrieve_memories(self,
                          query: str = "",
                          top_k: int = 3,
                          filter_dict: Dict[str, List[str]] = None) -> List[MemoryNode]:
        pass

    async def a_retrieve_memories(self,
                                  query: str = "",
                                  top_k: int = 3,
                                  filter_dict: Dict[str, List[str]] = None) -> List[MemoryNode]:
        pass

    def batch_insert(self, nodes: List[MemoryNode]):
        pass

    def batch_update(self, nodes: List[MemoryNode], update_embedding: bool = True):
        pass

    def batch_delete(self, nodes: List[MemoryNode]):
        pass

    def close(self):
        pass
