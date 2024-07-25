from typing import List

from memoryscope.enumeration.action_status_enum import ActionStatusEnum
from memoryscope.enumeration.memory_type_enum import MemoryTypeEnum
from memoryscope.memory.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.scheme.memory_node import MemoryNode
from memoryscope.utils.datetime_handler import DatetimeHandler


class UpdateMemoryWorker(MemoryBaseWorker):

    def _parse_params(self, **kwargs):
        self.method: str = kwargs.get("method", "")
        self.memory_key: str = kwargs.get("memory_key", "")

    def from_query(self):
        """
        Creates a MemoryNode from the provided query if present in chat_kwargs.

        Returns:
            List[MemoryNode]: A list containing a single MemoryNode created from the query.
        """
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
        """
        Retrieves memories based on the memory key if it exists.

        Returns:
            List[MemoryNode]: A list of MemoryNode objects retrieved using the memory key.
        """
        if not self.memory_key:
            return

        return self.memory_handler.get_memories(keys=self.memory_key)

    def delete_all(self):
        """
        Marks all memories for deletion by setting their action_status to 'DELETE'.

        Returns:
            List[MemoryNode]: A list of all MemoryNode objects marked for deletion.
        """
        nodes: List[MemoryNode] = self.memory_handler.get_memories(keys="all")
        for node in nodes:
            node.action_status = ActionStatusEnum.DELETE.value
        self.logger.info(f"delete_all.size={len(nodes)}")
        return nodes

    def delete_memory(self):
        """
        Marks specific memories for deletion based on query or memory_id present in chat_kwargs.

        Returns:
            List[MemoryNode]: A list of MemoryNode objects marked for deletion based on the query or memory_id.
        """
        if "query" in self.chat_kwargs:
            query = self.chat_kwargs["query"].strip()
            if not query:
                return

            i = 0
            nodes: List[MemoryNode] = self.memory_handler.get_memories(keys="all")
            for node in nodes:
                if node.content == query:
                    i += 1
                    node.action_status = ActionStatusEnum.DELETE.value
            self.logger.info(f"delete_memory.query.size={len(nodes)}")
            return nodes

        elif "memory_id" in self.chat_kwargs:
            memory_id = self.chat_kwargs["memory_id"].strip()
            if not memory_id:
                return

            i = 0
            nodes: List[MemoryNode] = self.memory_handler.get_memories(keys="all")
            for node in nodes:
                if node.memory_id == memory_id:
                    i += 1
                    node.action_status = ActionStatusEnum.DELETE.value
            self.logger.info(f"delete_memory.memory_id.size={len(nodes)}")
            return nodes

        return []

    def _run(self):
        """
        Executes a memory update method provided via the 'method' attribute.

        The method specified by the 'method' attribute is invoked,
        which updates memories accordingly.
        """
        method = self.method.strip()
        if not hasattr(self, method):
            self.logger.info(f"method={method} is missing!")
            return
        self.memory_handler.update_memories(nodes=getattr(self, method)())