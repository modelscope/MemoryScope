from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler


class StoreMemoryWorker(MemoryBaseWorker):

    def _run(self):
        store_key: str = self.store_key

        if store_key == "all":
            self.update_memories()

        elif self.has_content(store_key):
            self.update_memories(store_key)

        elif store_key in self.chat_kwargs:
            query = self.chat_kwargs[store_key]
            query = query.strip()
            if not query:
                return

            dt_handler = DatetimeHandler()
            node = MemoryNode(user_name=self.user_name,
                              target_name=self.target_name,
                              content=query,
                              memory_type=MemoryTypeEnum.OBS_CUSTOMIZED.value,
                              status=MemoryNodeStatus.NEW.value,
                              timestamp=dt_handler.timestamp,
                              obs_reflected=False,
                              obs_updated=False)
            self.memory_store.update_memories(node)
