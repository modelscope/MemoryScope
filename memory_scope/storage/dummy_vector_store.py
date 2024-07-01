from typing import Dict, List

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_vector_store import BaseVectorStore


class DummyVectorStore(BaseVectorStore):

    def __init__(self, embedding_model: BaseModel, **kwargs):
        self.embedding_model: BaseModel = embedding_model
        self.kwargs = kwargs

    def retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    async def async_retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    def insert(self, node: MemoryNode):
        pass
