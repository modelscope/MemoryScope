from memory_scope.enumeration.action_status_enum import ActionStatusEnum
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler


class StoreMemoryWorker(MemoryBaseWorker):

    def _run(self):
        if "query" in self.chat_kwargs:
            query = self.chat_kwargs["query"]
            query = query.strip()
            if not query:
                return

            dt_handler = DatetimeHandler()
            node = MemoryNode(user_name=self.user_name,
                              target_name=self.target_name,
                              content=query,
                              memory_type=MemoryTypeEnum.OBS_CUSTOMIZED.value,
                              action_status=ActionStatusEnum.NEW.value,
                              timestamp=dt_handler.timestamp)
            self.memory_handler.update_memories(nodes=node)
        else:
            self.memory_handler.update_memories(self.store_key)
