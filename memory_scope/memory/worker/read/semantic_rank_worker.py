from typing import List, Dict

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES, QUERY_WITH_TS, RANKED_MEMORY_NODES
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class SemanticRankWorker(MemoryBaseWorker):

    def _run(self):
        # query
        query, _ = self.get_context(QUERY_WITH_TS)
        memory_node_list: List[MemoryNode] = self.get_context(RETRIEVE_MEMORY_NODES)
        if not memory_node_list:
            self.logger.warning(f"retrieve memory nodes is empty!")
            return

        # solve content repeat, insight & profile has higher priority
        memory_node_dict: Dict[str, MemoryNode] = {}
        memory_type_selected = [MemoryTypeEnum.INSIGHT.value,
                                MemoryTypeEnum.PROFILE.value,
                                MemoryTypeEnum.PROFILE_CUSTOMIZED.value]
        for node in memory_node_list:
            if node.memory_type in memory_type_selected:
                return
            memory_node_dict[node.content] = node
        for node in memory_node_list:
            if node.memory_type not in memory_type_selected:
                return
            memory_node_dict[node.content] = node
        memory_node_list = list(memory_node_dict.values())

        response = self.rank_model.call(query=query, documents=[n.content for n in memory_node_list])

        if not response.status or not response.rank_scores:
            return

        # set score
        rank_memory_nodes: List[MemoryNode] = []
        rank_scores = sorted(response.rank_scores.items(), key=lambda x: x[1], reverse=True)
        for idx, score in rank_scores:
            if idx >= len(memory_node_list):
                self.logger.warning(f"idx={idx} exceeds the maximum length of the array")
                continue
            node = memory_node_list[idx]
            node.score_rank = score
            self.logger.info(f"rank_stage: content={node.content} score={node.score_rank}")
        self.get_context(RANKED_MEMORY_NODES, rank_memory_nodes)
