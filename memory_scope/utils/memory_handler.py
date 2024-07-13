from typing import Dict, List, Set

from memory_scope.enumeration.action_status_enum import ActionStatusEnum
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger


class MemoryHandler(object):

    def __init__(self):
        self._memory_store: BaseMemoryStore | None = None

        # dict: memory_id -> MemoryNode
        self._id_memory_dict: Dict[str, MemoryNode] = {}

        # dict: key -> memory_id
        self._key_id_dict: Dict[str, List[str]] = {}

        self.logger = Logger.get_logger()

    @property
    def memory_store(self) -> BaseMemoryStore:
        """
        Property to access the memory store. If not initialized, it fetches the memory store from the global context.

        Returns:
            BaseMemoryStore: The memory store instance associated with this worker.
        """
        if self._memory_store is None:
            self._memory_store = G_CONTEXT.memory_store
        return self._memory_store

    def clear(self):
        self._id_memory_dict.clear()
        self._key_id_dict.clear()

    def add_memories(self, nodes: MemoryNode | List[MemoryNode], log_repeat: bool = True):
        if nodes is None:
            nodes = []
        elif isinstance(nodes, MemoryNode):
            nodes = [nodes]

        for node in nodes:
            if node.memory_id in self._id_memory_dict:
                if log_repeat:
                    self.logger.warning(f"repeated_id memory id={node.memory_id} content={node.content} "
                                        f"status={node.status}")
                continue

            self._id_memory_dict[node.memory_id] = node
            self.logger.info(f"add to memory context memory id={node.memory_id} content={node.content} "
                             f"status={node.status}")

    def set_memories(self, key: str, nodes: MemoryNode | List[MemoryNode], log_repeat: bool = True):
        self.add_memories(nodes=nodes, log_repeat=log_repeat)
        self._key_id_dict[key] = [n.memory_id for n in nodes]

    def get_memories(self, keys: str | List[str]) -> List[MemoryNode]:
        """
        Retrieves memory nodes associated with the given keys.

        This method accepts a single key or a list of keys. For each key, it fetches the
        associated memory IDs from the context. If memory IDs are found, they are used to
        collect the corresponding MemoryNode objects from the contex_memory_dict. The final
        result is a list of unique MemoryNode values, avoiding duplicates.

        Args:
            keys (str | List[str]): The key or list of keys to retrieve memories for.

        Returns:
            List[MemoryNode]: A list of MemoryNode objects associated with the input keys.
        """
        memories: Dict[str, MemoryNode] = {}
        if isinstance(keys, str):
            keys = [keys]

        for key in keys:
            memory_ids: List[str] = self._key_id_dict[key]
            if memory_ids:
                memories.update({x: self._id_memory_dict[x] for x in memory_ids})
        return list(memories.values())

    def update_memories(self, keys: str | List[str] = None, nodes: MemoryNode | List[MemoryNode] = None):
        if keys is None:
            keys = []
        elif keys == "all":
            keys = list(self._id_memory_dict.keys())
        elif isinstance(keys, str):
            keys = [keys]

        # combine keys
        ids: Set[str] = set()
        for key in keys:
            t_ids: List[str] = self._key_id_dict[key]
            if t_ids:
                ids.update(t_ids)

        # Remove and collect nodes by IDs
        update_nodes: List[MemoryNode] = [self._id_memory_dict.pop(_) for _ in ids]

        if nodes is not None:
            if isinstance(nodes, MemoryNode):
                nodes = [nodes]
            update_nodes.extend(nodes)

        # Save collected nodes to memory store
        self._update_memories(update_nodes)

    def _update_memories(self, nodes: List[MemoryNode]):
        """
        Updates the memories based on their status:
        - New: Embeds and inserts the memory node.
        - Modified: Directly updates the memory node.
        - Content Modified: Embeds and then updates the memory node.
        - Active: No action required.
        - Expired: Updates the memory node.

        Args:
            nodes (List[MemoryNode]): A single memory node or a list of memory nodes to be updated.
        """
        if not nodes:
            return

        # emb & insert new memories
        new_memories = [n for n in nodes if n.action_status == ActionStatusEnum.NEW.value]
        if new_memories:
            for n in new_memories:
                n.action_status = ActionStatusEnum.NONE.value
            self.memory_store.batch_insert(new_memories)

        # emb & update new memories
        c_modified_memories = [n for n in nodes if n.action_status == ActionStatusEnum.CONTENT_MODIFIED]
        if c_modified_memories:
            for n in c_modified_memories:
                n.action_status = ActionStatusEnum.NONE.value
            self.memory_store.batch_update(c_modified_memories, update_embedding=True)

        # update new memories
        modified_memories = [n for n in nodes if n.action_status == ActionStatusEnum.MODIFIED]
        if modified_memories:
            for n in modified_memories:
                n.action_status = ActionStatusEnum.NONE.value
            self.memory_store.batch_update(c_modified_memories, update_embedding=False)

        # set memories expired
        delete_memories = [n for n in nodes if n.action_status == ActionStatusEnum.DELETE]
        if delete_memories:
            self.memory_store.batch_delete(nodes)
