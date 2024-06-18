from typing import List

from constants.common_constants import NEW, NEW_OBS_NODES
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory.memory_wrap_node import MemoryWrapNode
from worker.memory.memory_base_worker import MemoryBaseWorker


class EsNewObsWorker(MemoryBaseWorker):
    def __init__(self, es_new_obs_top_k, *args, **kwargs):
        super(EsNewObsWorker, self).__init__(*args, **kwargs)
        self.es_new_obs_top_k = es_new_obs_top_k

    def _run(self):
        hits = self.es_client.exact_search_v2(size=self.es_new_obs_top_k,
                                              term_filters={
                                                  "memoryId": self.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": MemoryTypeEnum.OBSERVATION.value,
                                                  f"metaData.{NEW}": "1",
                                              })

        new_obs_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        self.logger.info(f"es new obs, size={len(new_obs_nodes)}")
        self.set_context(NEW_OBS_NODES, new_obs_nodes)
