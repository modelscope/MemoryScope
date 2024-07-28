from typing import Dict, List

from memoryscope.constants.common_constants import EXTRACT_TIME_DICT, RANKED_MEMORY_NODES, RESULT
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.scheme.memory_node import MemoryNode


class FuseRerankWorker(MemoryBaseWorker):
    """
    Reranks the memory nodes by scores, types, and temporal relevance. Formats the top-K reranked nodes to print.
    """

    def _parse_params(self, **kwargs):
        self.fuse_score_threshold: float = kwargs.get("fuse_score_threshold", 0.1)
        self.fuse_ratio_dict: Dict[str, float] = kwargs.get("fuse_ratio_dict", {})
        self.fuse_time_ratio: float = kwargs.get("fuse_time_ratio", 2.0)
        self.fuse_rerank_top_k: int = kwargs.get("fuse_rerank_top_k", 10)

    @staticmethod
    def match_node_time(extract_time_dict: Dict[str, str], node: MemoryNode):
        """
        Determines whether the node is relevant.
        """
        if extract_time_dict:
            match_event_flag = True
            for k, v in extract_time_dict.items():
                event_value = node.meta_data.get(f"event_{k}", "")
                if event_value in ["-1", v]:
                    continue
                else:
                    match_event_flag = False
                    break

            match_msg_flag = True
            for k, v in extract_time_dict.items():
                msg_value = node.meta_data.get(f"msg_{k}", "")
                if msg_value == v:
                    continue
                else:
                    match_msg_flag = False
                    break
        else:
            match_event_flag = False
            match_msg_flag = False

        node.meta_data["match_event_flag"] = str(int(match_event_flag))
        node.meta_data["match_msg_flag"] = str(int(match_msg_flag))
        return match_event_flag, match_msg_flag

    def _run(self):
        """
        Executes the reranking process on memory nodes considering their scores, types, and temporal relevance.
        
        This method performs the following steps:
        1. Retrieves extraction time data and a list of ranked memory nodes from the worker's context.
        2. Reranks nodes based on a combination of their original rank score, type,
           and temporal alignment with extracted events/messages.
        3. Selects the top-K reranked nodes according to the predefined threshold.
        4. Optionally infuses inferred time information into the content of selected nodes.
        5. Logs reranking details and formats the final list of memories for output.
        """
        # Parse input parameters from the worker's context
        extract_time_dict: Dict[str, str] = self.get_context(EXTRACT_TIME_DICT)
        memory_node_list: List[MemoryNode] = self.memory_manager.get_memories(RANKED_MEMORY_NODES)

        # Check if memory nodes are available; warn and return if not
        if not memory_node_list:
            self.logger.warning("Ranked memory nodes list is empty.")
            return

        # Perform reranking based on score, type, and time relevance
        reranked_memory_nodes = []
        for node in memory_node_list:
            # Skip nodes below the fuse score threshold
            if node.score_rank < self.fuse_score_threshold:
                continue

            # Calculate type-based adjustment factor
            if node.memory_type not in self.fuse_ratio_dict:
                self.logger.warning(f"{node.memory_type} 'factor is not configured!")
            type_ratio: float = self.fuse_ratio_dict.get(node.memory_type, 0.1)

            # Determine time relevance adjustment factor
            match_event_flag, match_msg_flag = self.match_node_time(extract_time_dict=extract_time_dict, node=node)
            fuse_time_ratio: float = self.fuse_time_ratio if match_event_flag or match_msg_flag else 1.0

            # Apply reranking score adjustments
            node.score_rerank = node.score_rank * type_ratio * fuse_time_ratio
            reranked_memory_nodes.append(node)

        # build result
        memories: List[str] = []
        reranked_memory_nodes = sorted(reranked_memory_nodes,
                                       key=lambda x: x.score_rerank,
                                       reverse=True)[: self.fuse_rerank_top_k]
        for i, node in enumerate(reranked_memory_nodes):
            # Log reranking details including flags for event and message matches
            self.logger.info(f"Rerank Stage: Content={node.content}, Score={node.score_rerank}, "
                             f"Event Flag={node.meta_data['match_event_flag']}, "
                             f"Message Flag={node.meta_data['match_msg_flag']}")

            time_str = DatetimeHandler(node.timestamp).datetime_format("%Y%m%d-%H:%M:%S")
            memories.append(f"{i} {time_str} {node.content}")

        # Set the final list of formatted memories back into the worker's context
        self.set_context(RESULT, "\n".join(memories))
