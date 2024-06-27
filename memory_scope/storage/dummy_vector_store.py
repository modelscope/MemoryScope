from typing import Dict, List

from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_vector_store import BaseVectorStore


class DummyVectorStore(BaseVectorStore):
    def retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        pass

    async def async_retrieve(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]):
        pass

    def insert(self, node: MemoryNode):
        pass

    def insert_batch(self):
        pass

    def delete(self):
        pass

    def flush(self):
        pass
