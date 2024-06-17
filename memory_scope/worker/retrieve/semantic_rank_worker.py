from typing import List, Dict

from common.user_profile_handler import UserProfileHandler
from constants.common_constants import SIMILAR_OBS_NODES, RECALL_TYPE, KEYWORD_OBS_NODES, ALL_ONLINE_NODES, \
    QUERY_KEYWORDS
from enumeration.memory_recall_type import MemoryRecallType
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class SemanticRankWorker(MemoryBaseWorker):

    def user_profile_to_nodes(self) -> List[MemoryWrapNode]:
        user_profile_nodes: List[MemoryWrapNode] = UserProfileHandler.to_nodes(self.user_profile_dict, split_value=True)
        for node in user_profile_nodes:
            # 从画像侧召回
            node.memory_node.metaData[RECALL_TYPE] = MemoryRecallType.PROFILE
            self.logger.info(f"user profile node={node.memory_node.content}")
        return user_profile_nodes

    def _run(self):
        all_node_dict: Dict[str, MemoryWrapNode] = {}

        # 优先级: similar_obs_nodes < keyword_obs_nodes < profile_nodes
        similar_obs_nodes: List[MemoryWrapNode] = self.get_context(SIMILAR_OBS_NODES)
        if similar_obs_nodes:
            for node in similar_obs_nodes:
                all_node_dict[node.memory_node.content] = node

        keyword_obs_nodes: List[MemoryWrapNode] = self.get_context(KEYWORD_OBS_NODES)
        if keyword_obs_nodes:
            for node in keyword_obs_nodes:
                all_node_dict[node.memory_node.content] = node

        profile_nodes: List[MemoryWrapNode] = self.user_profile_to_nodes()
        if profile_nodes:
            for node in profile_nodes:
                all_node_dict[node.memory_node.content] = node

        if not all_node_dict:
            self.add_run_info(f"all_node_dict is empty!", continue_run=False)
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
        result = self.rerank_client.call(query=query, documents=documents)

        if not result:
            self.add_run_info(f"semantic call recall model failed!")
            return

        # set score
        for rank_node in result:
            content = documents[rank_node["index"]]
            node = all_node_dict[content]
            node.score_rank = rank_node["relevance_score"]
            self.logger.info(f"query={query} content={node.memory_node.content} score_rank={node.score_rank}")

        # save context
        all_online_nodes: List[MemoryWrapNode] = list(all_node_dict.values())
        self.set_context(ALL_ONLINE_NODES, all_online_nodes)
