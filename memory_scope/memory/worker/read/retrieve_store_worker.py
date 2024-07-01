from typing import List

from memory_scope.constants.common_constants import QUERY_WITH_TS, RETRIEVE_MEMORY_NODES
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class RetrieveStoreWorker(MemoryBaseWorker):

    async def retrieve_from_observation(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_id": self.user_id,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
        }
        return await self.vector_store.async_retrieve(query=query,
                                                      top_k=self.retrieve_obs_top_k,
                                                      filter_dict=filter_dict)

    async def retrieve_from_insight_and_profile(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_id": self.user_id,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.INSIGHT.value, MemoryTypeEnum.PROFILE.value],
        }
        return await self.vector_store.async_retrieve(query=query,
                                                      top_k=self.retrieve_ins_pf_top_k,
                                                      filter_dict=filter_dict)

    def _run(self):
        query, _ = self.get_context(QUERY_WITH_TS)
        memory_node_list: List[MemoryNode] = []
        fn_list = [self.retrieve_from_observation, self.retrieve_from_insight_and_profile]
        for result in self._async_run(fn_list=fn_list, query=query):
            if result:
                memory_node_list.extend(result)
        memory_node_list = sorted(memory_node_list, key=lambda x: x.score_similar, reverse=True)

        self.logger.info(f"memory_node_list.size={len(memory_node_list)}")
        for i, node in enumerate(memory_node_list):
            self.logger.info(f"{i}: node={node.content} score={node.score_similar} type={node.memory_type}")
        self.set_context(RETRIEVE_MEMORY_NODES, memory_node_list)
