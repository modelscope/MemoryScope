from typing import List

from constants.common_constants import INSIGHT_NODES
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from node.memory_wrap_node import MemoryWrapNode
from worker.memory_base_worker import MemoryBaseWorker


class EsInsightWorker(MemoryBaseWorker):
    def __init__(self, es_insight_top_k, *args, **kwargs):
        super(EsInsightWorker, self).__init__(*args, **kwargs)
        self.es_insight_top_k = es_insight_top_k

    def _run(self):
        hits = self.es_client.exact_search_v2(size=self.es_insight_top_k,
                                              term_filters={
                                                  "memoryId": self.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": MemoryTypeEnum.INSIGHT.value,
                                              })

        insight_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        self.logger.info(f"insight_nodes.size={len(insight_nodes)}")
        self.set_context(INSIGHT_NODES, insight_nodes)
