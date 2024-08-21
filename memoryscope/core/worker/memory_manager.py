from typing import Dict, List

from memoryscope.core.memoryscope_context import MemoryscopeContext
from memoryscope.core.storage.base_memory_store import BaseMemoryStore
from memoryscope.core.utils.logger import Logger
from memoryscope.enumeration.action_status_enum import ActionStatusEnum
from memoryscope.enumeration.store_status_enum import StoreStatusEnum
from memoryscope.scheme.memory_node import MemoryNode


class MemoryManager(object):
    """
    The `MemoryHandler` class manages memory nodes with memory store.
    """

    def __init__(self, memoryscope_context: MemoryscopeContext, workerflow_name: str ="default_worker"):
        self.memoryscope_context: MemoryscopeContext = memoryscope_context

        self._memory_store: BaseMemoryStore | None = None

        # dict: memory_id -> MemoryNode
        self._id_memory_dict: Dict[str, MemoryNode] = {}

        # dict: key -> memory_id
        self._key_id_dict: Dict[str, List[str]] = {}

        self.logger = Logger.get_logger("memory_manager")

        self.workerflow_name = workerflow_name


    @property
    def memory_store(self) -> BaseMemoryStore:
        """
        Property to access the memory store. If not initialized, it fetches the memory store from the global context.

        Returns:
            BaseMemoryStore: The memory store instance associated with this worker.
        """
        if self._memory_store is None:
            self._memory_store = self.memoryscope_context.memory_store
        return self._memory_store

    def clear(self):
        """
        Clear all memory nodes cached, reset the class instance.
        """
        self._id_memory_dict.clear()
        self._key_id_dict.clear()

    def add_memories(self, key: str, nodes: MemoryNode | List[MemoryNode], log_repeat: bool = True):
        """
        Add the memories.

        Args:
            key (str): The key mapping to memory nodes.
            nodes (List[MemoryNode]): A single memory node or a list of memory nodes to be updated.
            log_repeat (bool): Log duplicated memory node or not.
        """
        if key not in self._key_id_dict:
            return self.set_memories(key, nodes, log_repeat)

        if isinstance(nodes, MemoryNode):
            nodes = [nodes]

        for node in nodes:
            _id = node.memory_id
            if _id not in self._key_id_dict[key]:
                self._key_id_dict[key].append(_id)

            if _id not in self._id_memory_dict:
                self._id_memory_dict[_id] = node
                self.logger.info(f"add to memory context memory id={node.memory_id} content={node.content or node.key} "
                                 f"store_status={node.store_status} action_status={node.action_status}")

    def set_memories(self, key: str, nodes: MemoryNode | List[MemoryNode], log_repeat: bool = True):
        """
        Add the memories into '_id_memory_dict' and '_key_id_dict'.

        Args:
            key (str): The key mapping to memory nodes.
            nodes (List[MemoryNode]): A single memory node or a list of memory nodes to be updated.
            log_repeat: if log_repeat=True, print log info
        """
        if nodes is None:
            nodes = []
        elif isinstance(nodes, MemoryNode):
            nodes = [nodes]

        for node in nodes:
            if node.memory_id in self._id_memory_dict:
                if log_repeat:
                    self.logger.debug(f"repeated_id memory id={node.memory_id} content={node.content} "
                                      f"store_status={node.store_status} action_status={node.action_status}")
                continue

            self._id_memory_dict[node.memory_id] = node
            self.logger.info(f"add to memory context memory id={node.memory_id} content={node.content} "
                             f"store_status={node.store_status} action_status={node.action_status}")

        self._key_id_dict[key] = [n.memory_id for n in nodes]
        
        if nodes:
            self.logger.info(
                self.logger.wrap_in_box(
                    '\n'.join([f"workerflow_name: {self.workerflow_name} | memory_type:{node.memory_type} | content:{node.content}" for node in nodes])
                )
            )


    def get_memories(self, keys: str | List[str]) -> List[MemoryNode]:
        """
        Fetch the memories by keys.

        Args:
            keys (str | List[str]): The key mapping to memory nodes.

        Returns:
            List[MemoryNode]: Memories mapped to the key.
        """
        memories: Dict[str, MemoryNode] = {}

        if isinstance(keys, str):
            keys = [keys]

        for key in keys:
            if key == "all":
                memories.update(self._id_memory_dict)
                break
            elif key not in self._key_id_dict:
                continue

            memory_ids: List[str] = self._key_id_dict.get(key.strip())
            if memory_ids:
                memories.update({x: self._id_memory_dict[x] for x in memory_ids if x in self._id_memory_dict})

        return list(memories.values())

    def delete_memories(self, nodes: MemoryNode | List[MemoryNode], key: str = None):
        """
        Delete the memories.

        Args:
            key (str): The key mapping to memory nodes.
            nodes (List[MemoryNode]): A single memory node or a list of memory nodes to be deleted.
        """
        if isinstance(nodes, MemoryNode):
            nodes = [nodes]

        for n in nodes:
            _id = n.memory_id
            if _id in self._id_memory_dict:
                self._id_memory_dict.pop(_id, None)

            if key is None:
                for _, id_list in self._key_id_dict.items():
                    if _id in id_list:
                        id_list.remove(_id)
            else:
                id_list = self._key_id_dict[key]
                if _id in id_list:
                    id_list.remove(_id)

    def update_memories(self, keys: str = "", nodes: MemoryNode | List[MemoryNode] = None) -> dict:
        """
        Update the memories.

        Args:
            keys (str): The memories.
            nodes (List[MemoryNode]): A single memory node or a list of memory nodes to be updated.
        """
        update_memories: Dict[str, MemoryNode] = {n.memory_id: n for n in self.get_memories(keys=keys)}

        if nodes is not None:
            if isinstance(nodes, MemoryNode):
                nodes = [nodes]
            update_memories.update({n.memory_id: n for n in nodes})

        # Save collected nodes to memory store
        return self._update_memories(list(update_memories.values()))

    def _update_memories(self, nodes: List[MemoryNode]) -> dict:
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
            return {}

        update_info_dict = {}
        for node in nodes:
            # Non-deleted expired memory nodes need to be changed to a modified state.
            if node.store_status == StoreStatusEnum.EXPIRED.value and node.action_status != ActionStatusEnum.DELETE:
                node.action_status = ActionStatusEnum.MODIFIED

        # emb & insert new memories
        new_memories = [n for n in nodes if n.action_status == ActionStatusEnum.NEW.value]
        if new_memories:
            for n in new_memories:
                n.action_status = ActionStatusEnum.NONE.value
            self.memory_store.batch_insert(new_memories)
            update_info_dict[ActionStatusEnum.NEW.value] = new_memories

        # emb & update new memories
        c_modified_memories = [n for n in nodes if n.action_status == ActionStatusEnum.CONTENT_MODIFIED]
        if c_modified_memories:
            for n in c_modified_memories:
                n.action_status = ActionStatusEnum.NONE.value
            self.memory_store.batch_update(c_modified_memories, update_embedding=True)
            update_info_dict[ActionStatusEnum.CONTENT_MODIFIED.value] = c_modified_memories

        # update new memories
        modified_memories = [n for n in nodes if n.action_status == ActionStatusEnum.MODIFIED]
        if modified_memories:
            for n in modified_memories:
                n.action_status = ActionStatusEnum.NONE.value
            self.memory_store.batch_update(modified_memories, update_embedding=False)
            update_info_dict[ActionStatusEnum.MODIFIED.value] = modified_memories

        # set memories expired
        delete_memories = [n for n in nodes if n.action_status == ActionStatusEnum.DELETE]
        if delete_memories:
            self.memory_store.batch_delete(delete_memories)
            update_info_dict[ActionStatusEnum.DELETE.value] = delete_memories

        return update_info_dict
