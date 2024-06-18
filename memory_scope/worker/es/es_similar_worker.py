from typing import List

from constants.common_constants import SIMILAR_OBS_NODES, RECALL_TYPE
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_recall_type import MemoryRecallType
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory.memory_wrap_node import MemoryWrapNode
from worker.memory.memory_base_worker import MemoryBaseWorker


class EsSimilarWorker(MemoryBaseWorker):
    def __init__(self, es_similar_top_k, *args, **kwargs):
        super(EsSimilarWorker, self).__init__(*args, **kwargs)
        self.es_similar_top_k = es_similar_top_k

    def _run(self):
        query = self.messages[-1].content
        hits = self.es_client.similar_search(text=query,
                                             size=self.es_similar_top_k,
                                             exact_filters={
                                                 "memoryId": self.memory_id,
                                                 "status": MemoryNodeStatus.ACTIVE.value,
                                                 "scene": self.scene.lower(),
                                                 "memoryType": [MemoryTypeEnum.OBSERVATION.value,
                                                                MemoryTypeEnum.INSIGHT.value,
                                                                MemoryTypeEnum.OBS_CUSTOMIZED.value],
                                             })

        # 初始化成MemoryWrapNode，并加入召回源的参数
        similar_obs_nodes: List[MemoryWrapNode] = []
        for hit in hits:
            node = MemoryWrapNode.init_from_es(hit)
            node.memory_node.metaData[RECALL_TYPE] = MemoryRecallType.SIMILAR.value
            similar_obs_nodes.append(node)
        self.logger.info(f"similar_obs_nodes.size={len(similar_obs_nodes)}")
        for node in similar_obs_nodes:
            self.logger.info(f"node={node.memory_node.content} score_similar={node.score_similar}")
        self.set_context(SIMILAR_OBS_NODES, similar_obs_nodes)
