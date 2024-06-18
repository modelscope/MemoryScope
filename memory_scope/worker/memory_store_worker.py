from typing import List

from utils.user_profile_handler import UserProfileHandler
from constants.common_constants import MODIFIED_MEMORIES, NEW_USER_PROFILE
from node.memory_node import MemoryNode
from node.memory_wrap_node import MemoryWrapNode
from node.user_attribute import UserAttribute
from worker.memory_base_worker import MemoryBaseWorker

class MemoryStoreWorker(MemoryBaseWorker):

    def _run(self):
        modified_memories: List[MemoryWrapNode] | List[MemoryNode] = self.get_context(MODIFIED_MEMORIES)
        if modified_memories:
            if isinstance(modified_memories[0], MemoryWrapNode):
                modified_memories = [n.memory_node for n in modified_memories]

            for n in modified_memories:
                if not n.id:
                    n.id = f"{n.memoryId}_{n.scene}_content_{n.content}"
                    n.code = n.id
                    # TODO add batch insert
                self.es_client.insert(n.id, body=n.model_dump(exclude=set("content_modified", )))
        else:
            self.logger.warning("modified_memories is empty!")

        new_user_profile: List[UserAttribute] = self.get_context(NEW_USER_PROFILE)
        if new_user_profile:
            new_user_nodes: List[MemoryNode] = [n.memory_node for n in UserProfileHandler.to_nodes(new_user_profile)]
            for n in new_user_nodes:
                self.es_client.insert(n.id, body=n.model_dump(exclude=set("content_modified", )))
        else:
            self.logger.warning("new_user_profile is empty!")
