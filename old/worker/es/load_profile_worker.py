from typing import List, Dict

from constants import common_constants
from enumeration.memory_status_enum import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class LoadProfileWorker(MemoryBaseWorker):

    def _run(self):
        user_profile_node = self.vector_store(
            size=10000,
            filter_dict={
                "memory_id": self.memory_id,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memory_type": [
                    MemoryTypeEnum.PROFILE.value,
                    MemoryTypeEnum.PROFILE_CUSTOMIZED.value,
                ],
            },
        )
        self.set_context(common_constants.USER_PROFILE, user_profile_node)
        self.logger.info(f"retrieve_user_profile.size={len(user_profile_node)}")
