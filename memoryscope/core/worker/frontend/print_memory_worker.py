from typing import List

from memoryscope.constants.common_constants import RETRIEVE_MEMORY_NODES, RESULT
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.memory_type_enum import MemoryTypeEnum
from memoryscope.enumeration.store_status_enum import StoreStatusEnum
from memoryscope.scheme.memory_node import MemoryNode


class PrintMemoryWorker(MemoryBaseWorker):
    """
    Formats the memories to print.
    """
    FILE_PATH: str = __file__

    def _run(self):
        """
        Executes the primary function, it involves:
        1. Fetches the memories.
        2. Formats them by 'print_template'.
        3. Set the formatted string back into the worker's context
        """
        # get long-term memory
        memory_node_list: List[MemoryNode] = self.memory_manager.get_memories(RETRIEVE_MEMORY_NODES)
        memory_node_list = sorted(memory_node_list, key=lambda x: x.timestamp, reverse=True)

        observation_memory_list: List[str] = []
        insight_memory_list: List[str] = []
        expired_memory_list: List[str] = []

        i = 0
        j = 0
        k = 0
        # remove duplicate content
        expired_content_set = set()
        for node in memory_node_list:
            if not node.content:
                continue

            dt_handler = DatetimeHandler(node.timestamp)
            dt = dt_handler.datetime_format("%Y%m%d %H:%M:%S")
            if StoreStatusEnum(node.store_status) is StoreStatusEnum.EXPIRED:
                if node.content in expired_content_set:
                    continue
                else:
                    expired_content_set.add(node.content)
                    i += 1
                    expired_memory_list.append(f"{dt}] {i}. {node.content}")

            elif MemoryTypeEnum(node.memory_type) in [MemoryTypeEnum.OBSERVATION, MemoryTypeEnum.OBS_CUSTOMIZED]:
                j += 1
                observation_memory_list.append(f"{dt}] {j}. {node.content} "
                                               f"[status({node.obs_reflected},{node.obs_updated})")

            elif MemoryTypeEnum(node.memory_type) is MemoryTypeEnum.INSIGHT:
                k += 1
                insight_memory_list.append(f"{dt}] {k}. {node.content}")

        result: str = self.prompt_handler.print_template.format(
            user_name=self.user_name,
            target_name=self.target_name,
            observation_memory="\n".join(observation_memory_list),
            insight_memory="\n".join(insight_memory_list),
            expired_memory="\n".join(expired_memory_list)).strip()
        self.set_workflow_context(RESULT, result)
