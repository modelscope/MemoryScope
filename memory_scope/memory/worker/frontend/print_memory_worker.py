from typing import List

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES, RESULT
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.enumeration.store_status_enum import StoreStatusEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler


class PrintMemoryWorker(MemoryBaseWorker):

    def _run(self):
        memory_node_list: List[MemoryNode] = self.memory_handler.get_memories(RETRIEVE_MEMORY_NODES)
        memory_node_list = sorted(memory_node_list, key=lambda x: x.timestamp, reverse=True)

        expired_content_list: List[str] = ["----- expired -----"]
        obs_content_list: List[str] = ["----- observation -----"]
        insight_content_list: List[str] = ["----- insight -----"]
        i = 0
        j = 0
        k = 0
        expired_content_set = set()
        for node in memory_node_list:
            dt_handler = DatetimeHandler(node.timestamp)
            dt = dt_handler.datetime_format("%Y%m%d-%H:%M:%S")
            line = f"{dt} {node.content}"
            if StoreStatusEnum(node.store_status) is StoreStatusEnum.EXPIRED:
                if node.content in expired_content_set:
                    continue
                else:
                    expired_content_set.add(node.content)
                    i += 1
                    expired_content_list.append(f"  {i} {line}")

            elif MemoryTypeEnum(node.memory_type) in [MemoryTypeEnum.OBSERVATION, MemoryTypeEnum.OBS_CUSTOMIZED]:
                j += 1
                obs_content_list.append(f"  {j} {line}    status={node.obs_reflected},{node.obs_updated}")

            elif MemoryTypeEnum(node.memory_type) is MemoryTypeEnum.INSIGHT:
                k += 1
                insight_content_list.append(f"  {k} {line}")

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
