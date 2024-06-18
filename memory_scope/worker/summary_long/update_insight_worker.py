from typing import List

from common.response_text_parser import ResponseTextParser
from constants.common_constants import INSIGHT_NODES, NEW_OBS_NODES, INSIGHT_KEY, INSIGHT_VALUE
from node.memory_wrap_node import MemoryWrapNode
from worker.memory_base_worker import MemoryBaseWorker


class UpdateInsightWorker(MemoryBaseWorker):
    def __init__(update_insight_threshold, update_insight_max_thread, update_insight_model, update_insight_max_token, update_insight_temperature, update_insight_top_k,*args, **kwargs):
        super(UpdateInsightWorker, self).__init__(*args, **kwargs)
        self.update_insight_threshold = update_insight_threshold
        self.update_insight_max_thread = update_insight_max_thread
        self.update_insight_model = update_insight_model
        self.update_insight_max_token = update_insight_max_token
        self.update_insight_temperature = update_insight_temperature
        self.update_insight_top_k = update_insight_top_k

    def filter_obs_nodes(self,
                         insight_node: MemoryWrapNode,
                         new_obs_nodes: List[MemoryWrapNode]) -> (MemoryWrapNode, List[MemoryWrapNode], float):
        max_score: float = 0
        filtered_nodes: List[MemoryWrapNode] = []

        insight_key = insight_node.memory_node.metaData.get(INSIGHT_KEY, "")
        insight_value = insight_node.memory_node.metaData.get(INSIGHT_VALUE, "")
        if not insight_key or not insight_value:
            self.logger.warning(f"insight_key={insight_key} insight_value={insight_value} is empty!")
            return insight_node, filtered_nodes, max_score

        result = self.rerank_client.call(query=insight_key,
                                         documents=[x.memory_node.content for x in new_obs_nodes])

        if not result:
            self.add_run_info(f"update_insight={insight_key} call rerank failed!")
            return insight_node, filtered_nodes, max_score

        # 找到大于阈值的obs node

        for rank_node in result:
            index = rank_node["index"]
            score = rank_node["relevance_score"]
            node = new_obs_nodes[index]
            keep_flag = "filtered"
            if score >= self.update_insight_threshold:
                filtered_nodes.append(node)
                keep_flag = "keep"
                max_score = max(max_score, score)
            self.logger.info(f"insight_key={insight_key} insight_value={insight_value} "
                             f"score={score} keep_flag={keep_flag}")

        if not filtered_nodes:
            self.logger.info(f"update_insight={insight_key} filtered_nodes is empty!")

        return insight_node, filtered_nodes, max_score

    def update_insight(self,
                       insight_node: MemoryWrapNode,
                       filtered_nodes: List[MemoryWrapNode]) -> MemoryWrapNode:

        insight_key = insight_node.memory_node.metaData.get(INSIGHT_KEY, "")
        insight_value = insight_node.memory_node.metaData.get(INSIGHT_VALUE, "")
        self.logger.info(f"update_insight insight_key={insight_key} insight_value={insight_value} "
                         f"doc.size={len(filtered_nodes)}")

        # gen prompt
        user_query_list = []
        for node in filtered_nodes:
            user_query_list.append(f"句子：{node.memory_node.content}")
        update_insight_message = self.prompt_to_msg(
            system_prompt=self.prompt_config.update_insight_system,
            few_shot=self.prompt_config.update_insight_few_shot,
            user_query=self.prompt_config.update_insight_user_query.format(
                user_query="\n".join(user_query_list),
                insight_key=insight_key,
                insight_key_value=insight_key + "：" + insight_value))
        self.logger.info(f"update_insight_message={update_insight_message}")

        # call LLM
        response_text: str = self.gene_client.call(messages=update_insight_message,
                                                   model_name=self.update_insight_model,
                                                   max_token=self.update_insight_max_token,
                                                   temperature=self.update_insight_temperature,
                                                   top_k=self.update_insight_top_k)

        # return if empty
        if not response_text:
            self.add_run_info(f"update_insight insight_key={insight_key} call llm failed!")
            return insight_node

        profile_list = ResponseTextParser(response_text).parse_v1(f"update_profile {insight_key}")
        if not profile_list:
            self.add_run_info(f"update_insight insight_key={insight_key} profile_list empty 1!")
            return insight_node
        profile_list = profile_list[0]
        if not profile_list:
            self.add_run_info(f"update_insight insight_key={insight_key} profile_list empty 2")
            return insight_node
        insight_value = profile_list[0]

        if not insight_value or insight_value in ["无", "重复"]:
            self.logger.info(f"insight_value={insight_value}, skip.")
            return insight_node

        insight_node.memory_node.metaData[INSIGHT_VALUE] = insight_value
        insight_node.memory_node.content_modified = True
        return insight_node

    def _run(self):
        # 获取新的obs和insight
        new_obs_nodes: List[MemoryWrapNode] = self.get_context(NEW_OBS_NODES)
        insight_nodes: List[MemoryWrapNode] = self.get_context(INSIGHT_NODES)
        if not new_obs_nodes:
            self.logger.info("new_obs_nodes is empty, stop update sights!")
            return
        if not insight_nodes:
            self.logger.info("insight_nodes is empty, stop update sights!")
            return

        # 提交打分任务
        for node in insight_nodes:
            self.submit_thread(self.filter_obs_nodes,
                               sleep_time=0.1,
                               insight_node=node,
                               new_obs_nodes=new_obs_nodes)

        # 选择topN
        result_list = []
        for result in self.join_threads():
            insight_node, filtered_nodes, max_score = result
            if not filtered_nodes:
                continue
            result_list.append(result)
        result_sorted = sorted(result_list, key=lambda x: x[2], reverse=True)
        if len(result_sorted) > self.update_insight_max_thread:
            result_sorted = result_sorted[:update_insight_max_thread]

        # 提交LLM update任务
        for insight_node, filtered_nodes, _ in result_sorted:
            self.submit_thread(self.update_insight,
                               sleep_time=1,
                               insight_node=insight_node,
                               filtered_nodes=filtered_nodes)

        # 等待结果
        for result in self.join_threads():
            if result:
                insight_node: MemoryWrapNode = result
                insight_key = insight_node.memory_node.metaData.get(INSIGHT_KEY, "")
                insight_value = insight_node.memory_node.metaData.get(INSIGHT_VALUE, "")
                self.logger.info(f"after_update_insight insight_key={insight_key} insight_value={insight_value}")
