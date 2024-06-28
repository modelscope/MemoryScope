from typing import List

from constants.common_constants import SIMILAR_OBS_NODES, RECALL_TYPE
from enumeration.memory_status_enum import MemoryNodeStatus
from enumeration.memory_recall_type import MemoryRecallType
from enumeration.memory_type_enum import MemoryTypeEnum
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class EsSimilarWorker(MemoryBaseWorker):
    def __init__(self, es_similar_top_k, *args, **kwargs):
        super(EsSimilarWorker, self).__init__(*args, **kwargs)
        self.es_similar_top_k = es_similar_top_k

    def _run(self):
        query = self.messages[-1].content
        similar_obs_nodes = self.vector_store.retrieve(
            text=query,
            size=self.es_similar_top_k,
            filter_dict={
                "memory_id": self.memory_id,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memory_type": [
                    MemoryTypeEnum.OBSERVATION.value,
                    MemoryTypeEnum.INSIGHT.value,
                    MemoryTypeEnum.OBS_CUSTOMIZED.value,
                ],
            },
        )

        for node in similar_obs_nodes:
            node.meta_data[RECALL_TYPE] = MemoryRecallType.SIMILAR.value
        self.logger.info(f"similar_obs_nodes.size={len(similar_obs_nodes)}")
        for node in similar_obs_nodes:
            self.logger.info(f"node={node.content} score_similar={node.score_similar}")
        self.set_context(SIMILAR_OBS_NODES, similar_obs_nodes)
