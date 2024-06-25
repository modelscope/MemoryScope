from typing import List

from constants.common_constants import NEW, NEW_OBS_NODES
from enumeration.memory_status_enum import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class EsNewObsWorker(MemoryBaseWorker):
    def _run(self):
        new_obs_nodes = self.vector_store.retrieve(
            size=self.kwargs.es_new_obs_top_k,
            filter_dict={
                "memoryId": self.memory_id,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memoryType": MemoryTypeEnum.OBSERVATION.value,
                f"metaData.{NEW}": "1",
            },
        )
        self.logger.info(f"es new obs, size={len(new_obs_nodes)}")
        self.set_context(NEW_OBS_NODES, new_obs_nodes)
