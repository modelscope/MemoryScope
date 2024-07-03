from typing import List

from memory_scope.constants.common_constants import QUERY_WITH_TS, RETRIEVE_MEMORY_NODES
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class RetrieveStoreWorker(MemoryBaseWorker):

    async def retrieve_from_observation(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
        }
        return await self.vector_store.async_retrieve(query=query,
                                                      top_k=self.retrieve_obs_top_k,
                                                      filter_dict=filter_dict)

    async def retrieve_from_insight_and_profile(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.INSIGHT.value, MemoryTypeEnum.PROFILE.value],
        }
        return await self.vector_store.async_retrieve(query=query,
                                                      top_k=self.retrieve_ins_pf_top_k,
                                                      filter_dict=filter_dict)

    def _run(self):
        query, _ = self.get_context(QUERY_WITH_TS)
        self.submit_async_task(self.retrieve_from_observation, query=query)
        self.submit_async_task(self.retrieve_from_insight_and_profile, query=query)

        memory_node_list: List[MemoryNode] = []
        for result in self.gather_async_result():
            if result:
                memory_node_list.extend(result)
        self.logger.info(f"memory_node_list.size={len(memory_node_list)}")

        memory_node_list = sorted(memory_node_list, key=lambda x: x.score_similar, reverse=True)
        for node in memory_node_list:
            self.logger.info(f"recall_stage: content={node.content} score={node.score_similar} type={node.memory_type}")
        self.set_context(RETRIEVE_MEMORY_NODES, memory_node_list)
