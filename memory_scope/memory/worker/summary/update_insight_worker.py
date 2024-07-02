from typing import List

from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.constants.common_constants import (
    INSIGHT_NODES,
    NEW_OBS_NODES,
    INSIGHT_KEY,
    INSIGHT_VALUE,
)
from memory_scope.utils.tool_functions import prompt_to_msg
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.constants.language_constants import COMMA_WORD, COLON_WORD


class UpdateInsightWorker(MemoryBaseWorker):

    def filter_obs_nodes(
        self, insight_node: MemoryNode, new_obs_nodes: List[MemoryNode]
    ) -> (MemoryNode, List[MemoryNode], float):
        max_score: float = 0
        filtered_nodes: List[MemoryNode] = []

        insight_key = insight_node.meta_data.get(INSIGHT_KEY, "")
        insight_value = insight_node.meta_data.get(INSIGHT_VALUE, "")
        if not insight_key or not insight_value:
            self.logger.warning(
                f"insight_key={insight_key} insight_value={insight_value} is empty!"
            )
            return insight_node, filtered_nodes, max_score

        result = self.rank_model.call(
            query=insight_key, documents=[x.content for x in new_obs_nodes]
        )

        if not result:
            self.add_run_info(f"update_insight={insight_key} call rerank failed!")
            return insight_node, filtered_nodes, max_score

        # 找到大于阈值的obs node

        for index, score in result.rank_scores.items():
            node = new_obs_nodes[index]
            keep_flag = "filtered"
            if score >= self.update_insight_threshold:
                filtered_nodes.append(node)
                keep_flag = "keep"
                max_score = max(max_score, score)
            self.logger.info(
                f"insight_key={insight_key} insight_value={insight_value} "
                f"score={score} keep_flag={keep_flag}"
            )

        if not filtered_nodes:
            self.logger.info(f"update_insight={insight_key} filtered_nodes is empty!")

        return insight_node, filtered_nodes, max_score

    def update_insight(
        self, insight_node: MemoryNode, filtered_nodes: List[MemoryNode]
    ) -> MemoryNode:

        insight_key = insight_node.meta_data.get(INSIGHT_KEY, "")
        insight_value = insight_node.meta_data.get(INSIGHT_VALUE, "")
        self.logger.info(
            f"update_insight insight_key={insight_key} insight_value={insight_value} "
            f"doc.size={len(filtered_nodes)}"
        )

        # gen prompt
        user_query_list = []
        for node in filtered_nodes:
            user_query_list.append(self.prompt_handler.user_query.format(content=node.content))
        update_insight_message = prompt_to_msg(
            system_prompt=self.prompt_handler.system_prompt,
            few_shot=self.prompt_handler.few_shot_prompt,
            user_query=self.prompt_handler.user_query_prompt.format(
                user_query="\n".join(user_query_list),
                insight_key=insight_key,
                insight_key_value=insight_key + self.get_language_value(COLON_WORD) + insight_value,
            ),
        )
        self.logger.info(f"update_insight_message={update_insight_message}")

        # call LLM
        response: str = self.generation_model.call(
            messages=update_insight_message,
            model_name=self.update_insight_model,
            max_token=self.update_insight_max_token,
            temperature=self.update_insight_temperature,
            top_k=self.update_insight_top_k,
        )

        # return if empty
        if not response:
            self.add_run_info(
                f"update_insight insight_key={insight_key} call llm failed!"
            )
            return insight_node

        profile_list = ResponseTextParser(response.message.content).parse_v1(
            f"update_profile {insight_key}"
        )
        if not profile_list:
            self.add_run_info(
                f"update_insight insight_key={insight_key} profile_list empty 1!"
            )
            return insight_node
        profile_list = profile_list[0]
        if not profile_list:
            self.add_run_info(
                f"update_insight insight_key={insight_key} profile_list empty 2"
            )
            return insight_node
        insight_value = profile_list[0]

        if not insight_value or insight_value in self.prompt_handler.insight_value:
            self.logger.info(f"insight_value={insight_value}, skip.")
            return insight_node

        insight_node.meta_data[INSIGHT_VALUE] = insight_value
        insight_node.obs_updated = True
        return insight_node

    def _run(self):
        # 获取新的obs和insight
        new_obs_nodes: List[MemoryNode] = self.get_context(NEW_OBS_NODES)
        insight_nodes: List[MemoryNode] = self.get_context(INSIGHT_NODES)
        if not new_obs_nodes:
            self.logger.info("new_obs_nodes is empty, stop update sights!")
            return
        if not insight_nodes:
            self.logger.info("insight_nodes is empty, stop update sights!")
            return

        # 提交打分任务
        for node in insight_nodes:
            self.submit_thread(
                self.filter_obs_nodes,
                sleep_time=0.1,
                insight_node=node,
                new_obs_nodes=new_obs_nodes,
            )

        # 选择topN
        result_list = []
        for result in self.join_threads():
            insight_node, filtered_nodes, max_score = result
            if not filtered_nodes:
                continue
            result_list.append(result)
        result_sorted = sorted(result_list, key=lambda x: x[2], reverse=True)
        if len(result_sorted) > self.update_insight_max_thread:
            result_sorted = result_sorted[: self.update_insight_max_thread]

        # 提交LLM update任务
        for insight_node, filtered_nodes, _ in result_sorted:
            self.submit_thread(
                self.update_insight,
                sleep_time=1,
                insight_node=insight_node,
                filtered_nodes=filtered_nodes,
            )

        # 等待结果
        for result in self.join_threads():
            if result:
                insight_node: MemoryNode = result
                insight_key = insight_node.meta_data.get(INSIGHT_KEY, "")
                insight_value = insight_node.meta_data.get(INSIGHT_VALUE, "")
                self.logger.info(
                    f"after_update_insight insight_key={insight_key} insight_value={insight_value}"
                )
