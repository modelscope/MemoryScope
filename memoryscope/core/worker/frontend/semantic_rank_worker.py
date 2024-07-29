from typing import List, Dict

from memoryscope.constants.common_constants import RETRIEVE_MEMORY_NODES, QUERY_WITH_TS, RANKED_MEMORY_NODES
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.scheme.memory_node import MemoryNode


class SemanticRankWorker(MemoryBaseWorker):
    """
    The `SemanticRankWorker` class processes queries by retrieving memory nodes,
    removing duplicates, ranking them based on semantic relevance using a model,
    assigning scores, sorting the nodes, and storing the ranked nodes back,
    while logging relevant information.
    """

    def _run(self):
        """
        Executes the primary workflow of the SemanticRankWorker which includes:
        - Retrieves query and timestamp from context.
        - Fetches memory nodes.
        - Removes duplicate nodes.
        - Ranks nodes semantically.
        - Assigns scores to nodes.
        - Sorts nodes by score.
        - Saves the ranked nodes back with logging.

        If no memory nodes are retrieved or if the ranking model fails,
        appropriate warnings are logged.
        """
        # query
        query, _ = self.get_context(QUERY_WITH_TS)
        memory_node_list: List[MemoryNode] = self.memory_manager.get_memories(RETRIEVE_MEMORY_NODES)
        if not memory_node_list:
            self.logger.warning("Retrieve memory nodes is empty!")
            return

        use_dummy_ranker: bool = self.memoryscope_context.meta_data["use_dummy_ranker"]
        if use_dummy_ranker:
            for node in memory_node_list:
                node.score_rank = node.score_recall
            self.logger.warning("use score_recall instead of score_rank!")

        else:
            # drop repeated
            memory_node_dict: Dict[str, MemoryNode] = {n.content.strip(): n for n in memory_node_list if
                                                       n.content.strip()}
            memory_node_list = list(memory_node_dict.values())

            response = self.rank_model.call(query=query, documents=[n.content for n in memory_node_list])
            if not response.status or not response.rank_scores:
                return

            # set score
            for idx, score in response.rank_scores.items():
                if idx >= len(memory_node_list):
                    self.logger.warning(f"Idx={idx} exceeds the maximum length of rank_scores!")
                    continue
                memory_node_list[idx].score_rank = score

        # sort by score
        memory_node_list = sorted(memory_node_list, key=lambda n: n.score_rank, reverse=True)

        # log ranked nodes
        self.logger.info(f"Rank stage: query={query}")
        for node in memory_node_list:
            self.logger.info(f"Rank stage: Content={node.content}, Score={node.score_rank}")

        # save ranked nodes back to memory
        self.memory_manager.set_memories(RANKED_MEMORY_NODES, memory_node_list, log_repeat=False)
