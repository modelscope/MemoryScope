from typing import List

from common.tool_functions import time_to_formatted_str
from constants.common_constants import TODAY_OBS_NODES, DT
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class EsTodayObsWorker(MemoryBaseWorker):

    def _run(self):
        if not self.messages:
            self.logger.warning("messages is empty!")
            return
        msg_time_created = self.messages[-1].time_created
        hits = self.es_client.exact_search_v2(size=self.config.es_today_obs_top_k,
                                              term_filters={
                                                  "memoryId": self.config.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": MemoryTypeEnum.OBSERVATION.value,
                                                  f"metaData.{DT}": time_to_formatted_str(msg_time_created),
                                              })

        today_obs_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        self.logger.info(f"retrieve_today_obs.size={len(today_obs_nodes)}")
        self.set_context(TODAY_OBS_NODES, today_obs_nodes)
