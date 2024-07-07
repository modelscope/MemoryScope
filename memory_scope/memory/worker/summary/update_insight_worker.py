from typing import List

from memory_scope.constants.common_constants import INSIGHT_NODES, NOT_UPDATED_NODES, NOT_REFLECTED_NODES
from memory_scope.constants.language_constants import COLON_WORD, NONE_WORD, REPEATED_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class UpdateInsightWorker(MemoryBaseWorker):

    def filter_obs_nodes(self,
                         insight_node: MemoryNode,
                         obs_nodes: List[MemoryNode]) -> (MemoryNode, List[MemoryNode], float):
        max_score: float = 0
        filtered_nodes: List[MemoryNode] = []

        if not insight_node.key or not insight_node.value:
            self.logger.warning(f"insight_key={insight_node.key} insight_value={insight_node.value} is empty!")
            return insight_node, filtered_nodes, max_score

        response = self.rank_model.call(query=insight_node.key, documents=[x.content for x in obs_nodes])
        if not response.status:
            return insight_node, filtered_nodes, max_score

        # find nodes related to query
        for index, score in response.rank_scores.items():
            node = obs_nodes[index]
            keep_flag = score >= self.update_insight_threshold
            if keep_flag:
                filtered_nodes.append(node)
                max_score = max(max_score, score)
            self.logger.info(f"insight_key={insight_node.key} insight_value={insight_node.value} "
                             f"score={score} keep_flag={keep_flag}")

        if not filtered_nodes:
            self.logger.warning(f"update_insight={insight_node.key} filtered_nodes is empty!")
        return insight_node, filtered_nodes, max_score

    def update_insight_node(self, insight_node: MemoryNode, insight_value: str):
        dt_handler = DatetimeHandler()
        content = (f"{self.user_name}{self.get_language_value(COLON_WORD)}{insight_node.key}"
                   f"{self.get_language_value(COLON_WORD)}{insight_value}")
        insight_node.content = content
        insight_node.value = insight_value
        insight_node.meta_data.update({k: str(v) for k, v in dt_handler.dt_info_dict.items()})
        insight_node.timestamp = dt_handler.timestamp
        insight_node.dt = dt_handler.datetime_format()
        if insight_node.status == MemoryNodeStatus.ACTIVE.value:
            insight_node.status = MemoryNodeStatus.CONTENT_MODIFIED.value
        self.logger.info(f"after_update_{insight_node.key} value={insight_value}")
        return insight_node

    def update_insight(self, insight_node: MemoryNode, filtered_nodes: List[MemoryNode]) -> MemoryNode:
        self.logger.info(f"update_insight insight_key={insight_node.key} insight_value={insight_node.value} "
                         f"doc.size={len(filtered_nodes)}")

        # gen prompt
        user_query_list = [n.content for n in filtered_nodes]
        system_prompt = self.prompt_handler.update_insight_system.foramt(user_name=self.target_name)
        few_shot = self.prompt_handler.update_insight_few_shot.foramt(user_name=self.target_name)
        user_query = self.prompt_handler.update_insight_user_query.foramt(
            user_query="\n".join(user_query_list),
            insight_key=insight_node.key,
            insight_key_value=insight_node.key + self.get_language_value(COLON_WORD) + insight_node.value)

        update_insight_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"update_insight_message={update_insight_message}")

        # call LLM
        response = self.generation_model.call(messages=update_insight_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response.status or not response.message.content:
            return insight_node

        insight_value_list = ResponseTextParser(response.message.content).parse_v1(f"update_{insight_node.key}")
        if not insight_value_list:
            self.logger.warning(f"update_{insight_node.key} insight_value_list is empty!")
            return insight_node

        insight_value_list = insight_value_list[0]
        if not insight_value_list:
            self.logger.warning(f"update_{insight_node.key} insight_value_list is empty!")
            return insight_node

        insight_value = insight_value_list[0]
        if not insight_value or insight_value in self.get_language_value([NONE_WORD, REPEATED_WORD]):
            self.logger.info(f"update_{insight_node.key} insight_value={insight_value} is invalid.")
            return insight_node

        if insight_node.value == insight_value:
            self.logger.info(f"value={insight_value} is same!")
            return insight_node

        self.update_insight_node(insight_node=insight_node, insight_value=insight_value)
        return insight_node

    def _run(self):
        insight_nodes: List[MemoryNode] = self.get_context(INSIGHT_NODES)
        not_updated_nodes: List[MemoryNode] = self.get_context(NOT_UPDATED_NODES)
        not_reflected_nodes: List[MemoryNode] = self.get_context(NOT_REFLECTED_NODES)

        if not insight_nodes:
            self.logger.warning("insight_nodes is empty, stop.")
            return

        for node in insight_nodes:
            if node.status == MemoryNodeStatus.ACTIVE.value:
                self.submit_async_task(fn=self.filter_obs_nodes,
                                       insight_node=node,
                                       not_updated_nodes=not_updated_nodes)
            else:
                self.submit_async_task(fn=self.filter_obs_nodes,
                                       insight_node=node,
                                       not_updated_nodes=not_reflected_nodes)

        # select top n
        result_list = []
        for result in self.gather_async_result():
            insight_node, filtered_nodes, max_score = result
            if not filtered_nodes:
                continue
            result_list.append(result)
        result_sorted = sorted(result_list, key=lambda x: x[2], reverse=True)[: self.update_insight_max_thread]

        # submit llm update task
        for insight_node, filtered_nodes, _ in result_sorted:
            self.submit_async_task(fn=self.update_insight, insight_node=insight_node, filtered_nodes=filtered_nodes)

        # get result
        self.gather_async_result()

        for node in not_updated_nodes:
            node.obs_updated = True
