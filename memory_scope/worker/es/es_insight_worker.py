from typing import List

from constants.common_constants import INSIGHT_NODES
from enumeration.memory_status_enum import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker
from cli import GLOBAL_CONTEXT


class EsInsightWorker(MemoryBaseWorker):
    def _run(self):
        insight_nodes = self.vector_store.retrieve(
            size=self.kwargs.es_insight_top_k,
            filter_dict={
                "memoryId": self.memory_id,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memoryType": MemoryTypeEnum.INSIGHT.value,
            },
        )
        self.logger.info(f"insight_nodes.size={len(insight_nodes)}")
        self.set_context(INSIGHT_NODES, insight_nodes)
