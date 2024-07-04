from typing import List

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class ReadAllMemory(MemoryBaseWorker):

    def _run(self):
        memory_node_list: List[MemoryNode] = self.get_context(RETRIEVE_MEMORY_NODES)
        memory_node_list = sorted(memory_node_list, key=lambda x: x.timestamp, reverse=True)
        obs_content_list: List[str] = []

