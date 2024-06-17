from typing import List

from constants.common_constants import NEW, NEW_OBS_NODES
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class EsNewObsWorker(MemoryBaseWorker):

    def _run(self):
        hits = self.es_client.exact_search_v2(size=self.config.es_new_obs_top_k,
                                              term_filters={
                                                  "memoryId": self.config.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": MemoryTypeEnum.OBSERVATION.value,
                                                  f"metaData.{NEW}": "1",
                                              })

        new_obs_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        self.logger.info(f"es new obs, size={len(new_obs_nodes)}")
        self.set_context(NEW_OBS_NODES, new_obs_nodes)
