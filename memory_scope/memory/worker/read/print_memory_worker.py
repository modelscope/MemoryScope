from typing import List

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES, RESULT
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.timer import timer


class PrintMemoryWorker(MemoryBaseWorker):

    @timer
    def retrieve_expired_memory(self, query: str):
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.EXPIRED.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
        }
        return self.memory_store.retrieve_memories(query=query,
                                                   top_k=self.retrieve_expired_top_k,
                                                   filter_dict=filter_dict)

    def _run(self):
        expired_memories: List[MemoryNode] = self.retrieve_expired_memory(query="_")
        memory_node_list: List[MemoryNode] = self.get_memories(RETRIEVE_MEMORY_NODES)
        memory_node_list = sorted(memory_node_list, key=lambda x: x.timestamp, reverse=True)

        obs_content_list: List[str] = []
        insight_content_list: List[str] = []
        expired_content_list: List[str] = []
        i = 0
        j = 0
        for node in memory_node_list:

            if MemoryTypeEnum(node.memory_type) in [MemoryTypeEnum.OBSERVATION, MemoryTypeEnum.OBS_CUSTOMIZED]:
                i += 1
                dt_handler = DatetimeHandler(node.timestamp)
                dt = dt_handler.datetime_format("%Y%m%d %H:%M:%S")
                line = f"  {i} {dt} {node.content}"
                obs_content_list.append(line)

            elif MemoryTypeEnum(node.memory_type) in [MemoryTypeEnum.INSIGHT, ]:
                j += 1
                line = f"  {j} {node.content}"
                insight_content_list.append(line)

        for i, node in enumerate(expired_memories):
            line = f"  {j} {node.content}"
            expired_content_list.append(line)

        obs_content = "\n".join(obs_content_list)
        insight_content = "\n".join(insight_content_list)
        expired_content = "\n".join(expired_content_list)
        result: str = f"""
The memories of {self.user_name} about {self.target_name}.

----- observation -----
{obs_content}
----- observation -----

----- insight -----
{insight_content}
----- insight -----

----- expired -----
{expired_content}
----- expired -----
        """.strip()
        self.set_context(RESULT, result)
