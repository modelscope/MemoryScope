from typing import List

from memory_scope.constants.common_constants import NOT_REFLECTED_NODES, INSIGHT_NODES, MERGE_OBS_NODES, \
    NOT_UPDATED_NODES
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class SummaryCollectWorker(MemoryBaseWorker):

    def _run(self):
        keys = [
            INSIGHT_NODES,
            MERGE_OBS_NODES,
            NOT_UPDATED_NODES,
            NOT_REFLECTED_NODES,
        ]

        memory_nodes: List[MemoryNode] = []
        for key in keys:
            memory_nodes.extend(self.get_context(key))

        self.memory_store.update_memories(memory_nodes)
