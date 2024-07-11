from typing import List, Dict

from memory_scope.constants.common_constants import RETRIEVE_MEMORY_NODES, QUERY_WITH_TS, RANKED_MEMORY_NODES
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode


class SemanticRankWorker(MemoryBaseWorker):

    def _run(self):
        # query
        query, _ = self.get_context(QUERY_WITH_TS)
        memory_node_list: List[MemoryNode] = self.get_memories(RETRIEVE_MEMORY_NODES)
        if not memory_node_list:
            self.logger.warning(f"retrieve memory nodes is empty!")
            return

        # drop repeated
        memory_node_dict: Dict[str, MemoryNode] = {n.content: n for n in memory_node_list}
        memory_node_list = list(memory_node_dict.values())

        response = self.rank_model.call(query=query, documents=[n.content for n in memory_node_list])
        if not response.status or not response.rank_scores:
            return

        # set score
        for idx, score in response.rank_scores.items():
            if idx >= len(memory_node_list):
                self.logger.warning(f"idx={idx} exceeds the maximum length of rank_scores!")
                continue
            memory_node_list[idx].score_rank = score

        memory_node_list = sorted(memory_node_list, key=lambda n: n.score_rank, reverse=True)
        for node in memory_node_list:
            self.logger.info(f"rank_stage: content={node.content} score={node.score_rank}")
        self.set_memories(RANKED_MEMORY_NODES, memory_node_list, log_repeat=False)
