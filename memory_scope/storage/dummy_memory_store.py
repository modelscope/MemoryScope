from typing import Dict, List

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_memory_store import BaseMemoryStore


class DummyMemoryStore(BaseMemoryStore):

    def __init__(self, embedding_model: BaseModel, **kwargs):
        self.embedding_model: BaseModel = embedding_model
        self.kwargs = kwargs

    def retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    async def a_retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    def update_memories(self, nodes: MemoryNode | List[MemoryNode]):
        pass

    def close(self):
        pass
