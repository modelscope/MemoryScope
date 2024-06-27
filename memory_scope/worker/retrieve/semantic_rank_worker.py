from typing import List, Dict

from constants.common_constants import SIMILAR_OBS_NODES, RECALL_TYPE, KEYWORD_OBS_NODES, ALL_ONLINE_NODES, \
    QUERY_KEYWORDS
from enumeration.memory_recall_enum import MemoryRecallType
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class SemanticRankWorker(MemoryBaseWorker):

    def user_profile_to_nodes(self) -> List[MemoryNode]:
        user_profile_nodes: List[MemoryNode] = self.user_profile_dict
        for node in user_profile_nodes:
            # 从画像侧召回
            node.meta_data[RECALL_TYPE] = MemoryRecallType.PROFILE
            self.logger.info(f"user profile node={node.content}")
        return user_profile_nodes

    def _run(self):
        all_node_dict: Dict[str, MemoryNode] = {}

        # 优先级: similar_obs_nodes < profile_nodes
        similar_obs_nodes: List[MemoryNode] = self.get_context(SIMILAR_OBS_NODES)
        if similar_obs_nodes:
            for node in similar_obs_nodes:
                all_node_dict[node.content] = node

        profile_nodes: List[MemoryNode] = self.user_profile_to_nodes()
        if profile_nodes:
            for node in profile_nodes:
                all_node_dict[node.content] = node

        if not all_node_dict:
            self.add_run_info("all_node_dict is empty!", continue_run=False)
            return

        # call recall model
        query_keywords = self.get_context(QUERY_KEYWORDS)
        # TODO 根据效果更改
        # query: str = "用户：" + self.messages[-1].content
        query: str = self.messages[-1].content
        if query_keywords:
            query_keyword_join = "，".join(query_keywords)
            query = f"{query} 用户的{query_keyword_join}。"
        documents = list(all_node_dict.keys())
        result = self.rank_model.call(query=query, documents=documents)

        if not result:
            self.add_run_info("semantic call recall model failed!")
            return

        # set score
        for index, score in result.rank_scores.items():
            content = documents[index]
            node = all_node_dict[content]
            node.score_rank = score
            self.logger.info(f"query={query} content={node.content} score_rank={node.score_rank}")

        # save context
        all_online_nodes: List[MemoryNode] = list(all_node_dict.values())
        self.set_context(ALL_ONLINE_NODES, all_online_nodes)
