from typing import List

from memory_scope.constants.common_constants import NOT_REFLECTED_NODES, NOT_UPDATED_NODES, INSIGHT_NODES, TODAY_NODES
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.timer import timer


class LoadMemoryWorker(MemoryBaseWorker):

    @timer
    async def retrieve_not_reflected_memory(self, query: str):
        if not self.retrieve_not_reflected_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_reflected": False,
        }
        nodes: List[MemoryNode] = await self.memory_store.a_retrieve_memories(query=query,
                                                                              top_k=self.retrieve_not_reflected_top_k,
                                                                              filter_dict=filter_dict)
        self.set_memories(NOT_REFLECTED_NODES, nodes)

    @timer
    async def retrieve_not_updated_memory(self, query: str):
        if not self.retrieve_not_updated_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_updated": False,
        }
        nodes: List[MemoryNode] = await self.memory_store.a_retrieve_memories(query=query,
                                                                              top_k=self.retrieve_not_updated_top_k,
                                                                              filter_dict=filter_dict)
        self.set_memories(NOT_UPDATED_NODES, nodes)

    @timer
    async def retrieve_insight_memory(self, query: str):
        if not self.retrieve_insight_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": MemoryTypeEnum.INSIGHT.value,
        }
        nodes: List[MemoryNode] = await self.memory_store.a_retrieve_memories(query=query,
                                                                              top_k=self.retrieve_insight_top_k,
                                                                              filter_dict=filter_dict)
        self.set_memories(INSIGHT_NODES, nodes)

    @timer
    async def retrieve_today_memory(self):
        if not self.today_obs_top_k:
            return

        if not self.chat_messages:
            self.logger.warning("chat_messages is empty!")
            return

        message: Message = self.chat_messages[-1]
        dt_handler = DatetimeHandler(message.time_created)
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "dt": dt_handler.datetime_format(),
        }
        nodes: List[MemoryNode] = await self.memory_store.a_retrieve_memories(query=message.content,
                                                                              top_k=self.today_obs_top_k,
                                                                              filter_dict=filter_dict)

        self.set_memories(TODAY_NODES, nodes)

    async def _run(self):
        mock_query = "-"
        self.submit_async_task(self.retrieve_not_reflected_memory, query=mock_query)
        self.submit_async_task(self.retrieve_not_updated_memory, query=mock_query)
        self.submit_async_task(self.retrieve_insight_memory, query=mock_query)
        self.submit_async_task(self.retrieve_today_memory)
        self.gather_async_result()
