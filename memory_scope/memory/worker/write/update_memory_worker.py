from typing import Dict, List

from memory_scope.enumeration.action_status_enum import ActionStatusEnum
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.enumeration.store_status_enum import StoreStatusEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler


class UpdateMemoryWorker(MemoryBaseWorker):

    def _parse_params(self, **kwargs):
        self.method: str = kwargs.get("method", "")
        self.memory_key: str = kwargs.get("memory_key", "")
        self.expired_action: str = kwargs.get("expired_action", "")
        self.valid_action_dict: Dict[str, str] = kwargs.get("expired_action", {})

    def from_query(self):
        if "query" not in self.chat_kwargs:
            return

        query = self.chat_kwargs["query"].strip()
        if not query:
            return

        dt_handler = DatetimeHandler()
        node = MemoryNode(user_name=self.user_name,
                          target_name=self.target_name,
                          content=query,
                          memory_type=MemoryTypeEnum.OBS_CUSTOMIZED.value,
                          action_status=ActionStatusEnum.NEW.value,
                          timestamp=dt_handler.timestamp)
        return [node]

    def from_memory_key(self):
        if not self.memory_key:
            return

        return self.memory_handler.get_memories(keys=self.memory_key)

    def modify_action_status(self):
        nodes: List[MemoryNode] = self.memory_handler.get_memories(keys="all")
        for node in nodes:
            if self.expired_action and node.store_status == StoreStatusEnum.EXPIRED.value:
                node.action_status = self.expired_action

            elif node.memory_type in self.valid_action_dict:
                action_status = self.valid_action_dict[node.memory_type]
                if action_status:
                    node.action_status = action_status

        return nodes

    def _run(self):
        method = self.method.strip()
        if not hasattr(self, method):
            self.logger.info(f"method={method} is missing!")
            return
        self.memory_handler.update_memories(nodes=getattr(self, method)())
