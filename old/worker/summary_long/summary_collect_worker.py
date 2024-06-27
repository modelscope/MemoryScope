from typing import List, Dict

from ...constants.common_constants import (
    NEW_INSIGHT_NODES,
    MODIFIED_MEMORIES,
    INSIGHT_NODES,
    NEW_OBS_NODES,
    NOT_REFLECTED_OBS_NODES,
    NEW,
    NOT_REFLECTED_MERGE_NODES,
    CONTENT_MODIFIED,
)
from ...scheme.memory_node import MemoryNode
from ..memory_base_worker import MemoryBaseWorker


class SummaryCollectWorker(MemoryBaseWorker):

    def _run(self):
        insight_nodes: List[MemoryNode] = self.get_context(INSIGHT_NODES)
        new_insight_nodes: List[MemoryNode] = self.get_context(NEW_INSIGHT_NODES)
        new_obs_nodes: List[MemoryNode] = self.get_context(NEW_OBS_NODES)
        not_reflected_nodes: List[MemoryNode] = self.get_context(
            NOT_REFLECTED_OBS_NODES
        )
        not_reflected_merge_nodes: List[MemoryNode] = self.get_context(
            NOT_REFLECTED_MERGE_NODES
        )

        # 合并逻辑，复杂，务必check
        all_node_dict: Dict[str, MemoryNode] = {}
        if insight_nodes:
            all_node_dict.update(
                {n.id: n for n in insight_nodes if n.meta_data.get(CONTENT_MODIFIED, False)}
            )
        if new_insight_nodes:
            all_node_dict.update({n.content: n for n in new_insight_nodes})
        if new_obs_nodes:
            # 设置为非新
            for n in new_obs_nodes:
                n.meta_data[NEW] = "0"
            all_node_dict.update({n.content: n for n in new_obs_nodes})
        if not_reflected_merge_nodes and not_reflected_nodes:
            # 进入reflect阶段
            all_node_dict.update({n.id: n for n in not_reflected_nodes})

        self.set_context(MODIFIED_MEMORIES, list(all_node_dict.values()))
