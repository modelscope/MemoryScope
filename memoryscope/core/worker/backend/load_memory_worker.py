from typing import List

from memoryscope.constants.common_constants import NOT_REFLECTED_NODES, NOT_UPDATED_NODES, INSIGHT_NODES, TODAY_NODES
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.utils.timer import timer
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.memory_type_enum import MemoryTypeEnum
from memoryscope.enumeration.store_status_enum import StoreStatusEnum
from memoryscope.scheme.memory_node import MemoryNode


class LoadMemoryWorker(MemoryBaseWorker):
    def _parse_params(self, **kwargs):
        self.retrieve_not_reflected_top_k: int = kwargs.get("retrieve_not_reflected_top_k", 0)
        self.retrieve_not_updated_top_k: int = kwargs.get("retrieve_not_updated_top_k", 0)
        self.retrieve_insight_top_k: int = kwargs.get("retrieve_insight_top_k", 0)
        self.retrieve_today_top_k: int = kwargs.get("retrieve_today_top_k", 0)

    @timer
    def retrieve_not_reflected_memory(self):
        """
        Retrieves top-K not reflected memories based on the query and stores them in the memory handler.
        """
        if not self.retrieve_not_reflected_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "store_status": StoreStatusEnum.VALID.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_reflected": 0,
        }
        nodes: List[MemoryNode] = self.memory_store.retrieve_memories(top_k=self.retrieve_not_reflected_top_k,
                                                                      filter_dict=filter_dict)
        self.memory_manager.set_memories(NOT_REFLECTED_NODES, nodes)

    @timer
    def retrieve_not_updated_memory(self):
        """
        Retrieves top-K not updated memories based on the query and stores them in the memory handler.
        """
        if not self.retrieve_not_updated_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "store_status": StoreStatusEnum.VALID.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_updated": 0,
        }
        nodes: List[MemoryNode] = self.memory_store.retrieve_memories(top_k=self.retrieve_not_updated_top_k,
                                                                      filter_dict=filter_dict)
        self.memory_manager.set_memories(NOT_UPDATED_NODES, nodes)

    @timer
    def retrieve_insight_memory(self):
        """
        Retrieves top-K insight memories based on the query and stores them in the memory handler.
        """
        if not self.retrieve_insight_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "store_status": StoreStatusEnum.VALID.value,
            "memory_type": MemoryTypeEnum.INSIGHT.value,
        }
        nodes: List[MemoryNode] = self.memory_store.retrieve_memories(top_k=self.retrieve_insight_top_k,
                                                                      filter_dict=filter_dict)
        self.memory_manager.set_memories(INSIGHT_NODES, nodes)

    @timer
    def retrieve_today_memory(self, dt: str):
        """
        Retrieves top-K memories from today based on the query and stores them in the memory handler.

        Args:
            dt (str): The date string to filter today's memories.
        """
        if not self.retrieve_today_top_k:
            return

        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "store_status": StoreStatusEnum.VALID.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "dt": dt,
        }
        nodes: List[MemoryNode] = self.memory_store.retrieve_memories(top_k=self.retrieve_today_top_k,
                                                                      filter_dict=filter_dict)

        self.memory_manager.set_memories(TODAY_NODES, nodes)

    def _run(self):
        """
        Initiates multithread tasks to retrieve various types of memory data including
        not reflected, not updated, insights, and data from today. After submitting all tasks,
        it waits for their completion by calling `gather_thread_result`.

        This method serves as the controller for data retrieval operations, enhancing efficiency
        by handling tasks concurrently.
        """

        # Placeholder query
        dt = DatetimeHandler().datetime_format()
        self.submit_thread_task(self.retrieve_not_reflected_memory)
        self.submit_thread_task(self.retrieve_not_updated_memory)
        self.submit_thread_task(self.retrieve_insight_memory)
        self.submit_thread_task(self.retrieve_today_memory, dt=dt)

        # Waits for all submitted tasks to complete
        for _ in self.gather_thread_result():
            pass
