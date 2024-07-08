from typing import List, Dict

from memory_scope.constants.common_constants import NOT_REFLECTED_NODES, INSIGHT_NODES, MERGE_OBS_NODES, \
    NOT_UPDATED_NODES
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class SummaryCollectWorker(MemoryBaseWorker):

    def _run(self):
        update_memories: Dict[str, MemoryNode] = {}
        insight_nodes: List[MemoryNode] = self.get_context(INSIGHT_NODES)
        if insight_nodes:
            update_memories.update({n.memory_id: n for n in insight_nodes})

        not_reflected_nodes: List[MemoryNode] = self.get_context(NOT_REFLECTED_NODES)
        if not_reflected_nodes:
            update_memories.update({n.memory_id: n for n in not_reflected_nodes})

        not_updated_nodes: List[MemoryNode] = self.get_context(NOT_UPDATED_NODES)
        if not_updated_nodes:
            for node in not_updated_nodes:
                if node.memory_id in update_memories:




        keys = [
            INSIGHT_NODES,
            MERGE_OBS_NODES,
            NOT_UPDATED_NODES,
            NOT_REFLECTED_NODES,
        ]

        memory_nodes: List[MemoryNode] = []
        for key in keys:
            memory_nodes.extend(self.get_context(key))

        self.memory_store.update_memories(update_memories)
