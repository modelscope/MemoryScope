from typing import List

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES, RESULT
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler


class PrintMemoryWorker(MemoryBaseWorker):

    def _run(self):
        memory_node_list: List[MemoryNode] = self.get_memories(RETRIEVE_MEMORY_NODES)
        memory_node_list = sorted(memory_node_list, key=lambda x: x.timestamp, reverse=True)

        expired_content_list: List[str] = ["----- expired -----"]
        obs_content_list: List[str] = ["----- observation -----"]
        insight_content_list: List[str] = ["----- insight -----"]
        i = 0
        j = 0
        k = 0
        for node in memory_node_list:
            if MemoryNodeStatus(node.status) is MemoryNodeStatus.EXPIRED:
                i += 1
                line = f"  {i} {node.content}"
                expired_content_list.append(line)

            if MemoryTypeEnum(node.memory_type) in [MemoryTypeEnum.OBSERVATION, MemoryTypeEnum.OBS_CUSTOMIZED]:
                j += 1
                dt_handler = DatetimeHandler(node.timestamp)
                dt = dt_handler.datetime_format("%Y%m%d %H:%M:%S")
                line = f"  {j} {dt} {node.content}"
                obs_content_list.append(line)

            elif MemoryTypeEnum(node.memory_type) is MemoryTypeEnum.INSIGHT:
                k += 1
                line = f"  {k} {node.content}"
                insight_content_list.append(line)

        obs_content = "\n".join(obs_content_list)
        insight_content = "\n".join(insight_content_list)
        expired_content = "\n".join(expired_content_list)
        result: str = f"""
The memories of {self.user_name} about {self.target_name}.

{obs_content}


{insight_content}


{expired_content}
        """.strip()
        self.set_context(RESULT, result)
