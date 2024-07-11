from typing import Dict, List

from memory_scope.constants.common_constants import EXTRACT_TIME_DICT, RANKED_MEMORY_NODES, RESULT
from memory_scope.constants.language_constants import COLON_WORD
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler


class FuseRerankWorker(MemoryBaseWorker):

    @staticmethod
    def match_node_time(extract_time_dict: Dict[str, str], node: MemoryNode):
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
        # parse input
        extract_time_dict: Dict[str, str] = self.get_context(EXTRACT_TIME_DICT)
        memory_node_list: List[MemoryNode] = self.get_memories(RANKED_MEMORY_NODES)
        if not memory_node_list:
            self.logger.warning(f"ranked memory nodes is empty!")
            return

        # get reranked nodes
        reranked_memory_nodes = []
        for node in memory_node_list:
            if node.score_rank < self.fuse_score_threshold:
                continue

            # memory type ratio
            type_ratio: float = self.fuse_ratio_dict.get(node.memory_type, 0.1)

            # memory fuse time ratio
            match_event_flag, match_msg_flag = self.match_node_time(extract_time_dict=extract_time_dict, node=node)
            fuse_time_ratio: float = self.fuse_time_ratio if match_event_flag or match_msg_flag else 1.0

            # fuse rerank score
            node.score_rerank = node.score_rank * type_ratio * fuse_time_ratio
            reranked_memory_nodes.append(node)

        # build result
        memories: List[str] = []
        reranked_memory_nodes = sorted(reranked_memory_nodes,
                                       key=lambda x: x.score_rerank,
                                       reverse=True)[: self.fuse_rerank_top_k]
        for node in reranked_memory_nodes:
            f_event = int(node.meta_data["match_event_flag"])
            f_msg = int(node.meta_data["match_msg_flag"])
            self.logger.info(f"rerank_stage: content={node.content} score={node.score_rerank} "
                             f"f_event={f_event} f_msg={f_msg}")

            content = node.content
            if f_event or f_msg:
                time_infer = DatetimeHandler.format_time_by_extract_time(extract_time_dict=extract_time_dict,
                                                                         meta_data=node.memory_node.metaData)
                if time_infer:
                    content = f"{time_infer}{self.get_language_value(COLON_WORD)}{content}"
            memories.append(content)

        self.set_context(RESULT, "\n".join(memories))
