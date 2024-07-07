from typing import List

from constants.common_constants import REFLECTED, NOT_REFLECTED_OBS_NODES
from enumeration.memory_status_enum import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class EsNotReflectedWorker(MemoryBaseWorker):

    def _run(self):

        not_reflected_obs_nodes = self.vector_store.retrieve_memories(
            size=self.kwargs.es_new_obs_top_k,
            filter_dict={
                "memory_id": self.memory_id,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memory_type": [
                    MemoryTypeEnum.OBSERVATION.value,
                    MemoryTypeEnum.OBS_CUSTOMIZED.value,
                ],
                f"meta_data.{REFLECTED}": "0",
            },
        )
        self.logger.info(
            f"retrieve_not_reflected_obs.size={len(not_reflected_obs_nodes)}"
        )
        self.set_context(NOT_REFLECTED_OBS_NODES, not_reflected_obs_nodes)
