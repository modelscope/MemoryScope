from typing import List, Dict

from utils.user_profile_handler import UserProfileHandler
from constants import common_constants
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from node.memory_wrap_node import MemoryWrapNode
from node.user_attribute import UserAttribute
from pipeline.memory import MemoryServiceRequestModel
from worker.memory_base_worker import MemoryBaseWorker


class LoadProfileWorker(MemoryBaseWorker):

    def _run(self):
        hits = self.es_client.exact_search_v2(size=10000,
                                              term_filters={
                                                  "memoryId": self.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": [MemoryTypeEnum.PROFILE.value,
                                                                 MemoryTypeEnum.PROFILE_CUSTOMIZED.value],
                                              })

        user_profile_node: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        user_profile_dict: Dict[str, UserAttribute] = UserProfileHandler.to_user_attr(user_profile_node)

        request: MemoryServiceRequestModel = self.get_context(common_constants.REQUEST)
        for user_attr in request.user_profile:
            user_profile_dict[user_attr.memory_key] = user_attr
        request.user_profile = list(user_profile_dict.values())
        self.logger.info(f"retrieve_user_profile.size={len(user_profile_dict)}")
        for key, user_attr in user_profile_dict.items():
            self.logger.info(f"{key}: {user_attr.description}: {user_attr.value}")
