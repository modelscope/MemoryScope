from typing import List

from constants.common_constants import REFLECTED, NOT_REFLECTED_OBS_NODES
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class EsNotReflectedWorker(MemoryBaseWorker):
    def _run(self):
        hits = self.es_client.exact_search_v2(size=self.config.es_not_reflected_top_k,
                                              term_filters={
                                                  "memoryId": self.config.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": [MemoryTypeEnum.OBSERVATION.value,
                                                                 MemoryTypeEnum.OBS_CUSTOMIZED.value],
                                                  f"metaData.{REFLECTED}": "0",
                                              })

        not_reflected_obs_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        self.logger.info(f"retrieve_not_reflected_obs.size={len(not_reflected_obs_nodes)}")
        self.set_context(NOT_REFLECTED_OBS_NODES, not_reflected_obs_nodes)
