from typing import List, Dict

from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.timer import timer
from memory_scope.utils.global_context import G_CONTEXT

class LoadMemoryWorker(MemoryBaseWorker):

    @timer
    async def retrieve_not_reflected_memory(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_reflected": False,
        }
        return await self.vector_store.async_retrieve(query=query,
                                                      top_k=self.retrieve_not_reflected_top_k,
                                                      filter_dict=filter_dict)

    @timer
    async def retrieve_not_updated_memory(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_updated": False,
        }
        return await self.vector_store.async_retrieve(query=query,
                                                      top_k=self.retrieve_not_updated_top_k,
                                                      filter_dict=filter_dict)

    @timer
    async def retrieve_profiles(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.PROFILE.value, MemoryTypeEnum.PROFILE_CUSTOMIZED.value],
        }
        retrieve_nodes = await self.vector_store.async_retrieve(query=query,
                                                       top_k=self.retrieve_profiles_top_k,
                                                       filter_dict=filter_dict)
        nodes: List[MemoryNode] = []
        human_profile_setting = G_CONTEXT.meta_data.get("human_profile_setting", [])
        for attr_key in human_profile_setting:


        return nodes

    def _run(self):
        mock_query = "_"
        fn_list = [
            self.retrieve_not_reflected_memory,
            self.retrieve_not_updated_memory,
            self.retrieve_profiles,
        ]
        memory_node_dict: Dict[str, MemoryNode] = {}
        for nodes in self.async_run(fn_list, query=mock_query):
            assert isinstance(nodes[0], MemoryNode)
            memory_node_dict.update({n.memory_id: n for n in nodes})

        memory_node_list = sorted(memory_node_dict.values(), key=lambda x: x.memory_id)
