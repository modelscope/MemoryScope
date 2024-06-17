from typing import List

from constants.common_constants import ALL_NODES, ALL_MEMORIES
from enumeration.memory_node_status import MemoryNodeStatus
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class EsRetrieveAllWorker(MemoryBaseWorker):

    def _run(self):
        # msg_time_created = self.messages[-1].time_created
        hits = self.es_client.exact_search_v2(size=1000,
                                              term_filters={
                                                  "memoryId": self.config.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  # "memoryType": MemoryTypeEnum.OBSERVATION.value,
                                                  # f"metaData.{DT}": time_to_formatted_str(msg_time_created),
                                              })

        all_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(hit) for hit in hits]
        self.logger.info(f"retrieve_all.size={len(all_nodes)}")
        self.set_context(ALL_NODES, all_nodes)

        all_memories = []
        if all_nodes:
            for node in all_nodes:
                all_memories.append(node.memory_node.to_dict())
        self.set_context(ALL_MEMORIES, all_memories)