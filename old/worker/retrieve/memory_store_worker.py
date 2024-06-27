from typing import List

from utils.user_profile_handler import UserProfileHandler
from constants.common_constants import MODIFIED_MEMORIES, NEW_USER_PROFILE, CONTENT_MODIFIED
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class MemoryStoreWorker(MemoryBaseWorker):

    def _run(self):
        modified_memories: List[MemoryNode] | List[MemoryNode] = self.get_context(
            MODIFIED_MEMORIES
        )
        if modified_memories:
            if isinstance(modified_memories[0], MemoryNode):
                modified_memories = [n.memory_node for n in modified_memories]

            for n in modified_memories:
                if not n.id:
                    n.id = f"{n.memory_id}_content_{n.content}"
                    n.code = n.id
                    # TODO add batch insert
                n.meta_data.pop(CONTENT_MODIFIED)
                self.vector_store.insert(n)
        else:
            self.logger.warning("modified_memories is empty!")

        new_user_profile: List[MemoryNode] = self.get_context(NEW_USER_PROFILE)
        if new_user_profile:
            for n in new_user_profile:
                n.meta_data.pop(CONTENT_MODIFIED)
                self.vector_store.insert(n)
        else:
            self.logger.warning("new_user_profile is empty!")
