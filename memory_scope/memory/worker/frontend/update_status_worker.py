from typing import List

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES
from memory_scope.enumeration.store_status_enum import StoreStatusEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class UpdateStatusWorker(MemoryBaseWorker):
    def _run(self):
        expired_action = self.expired_action
        valid_action_dict: dict = self.valid_action_dict
        memory_node_list: List[MemoryNode] = self.memory_handler.get_memories(RETRIEVE_MEMORY_NODES)
        if not memory_node_list:
            return

        for node in memory_node_list:
            if node.store_status == StoreStatusEnum.EXPIRED.value:
                node.action_status = expired_action

            elif node.memory_type in valid_action_dict:
                node.action_status = valid_action_dict[node.memory_type]

        self.memory_handler.update_memories(nodes=memory_node_list)
