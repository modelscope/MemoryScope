from typing import List

from common.response_text_parser import ResponseTextParser
from constants.common_constants import NEW_OBS_NODES, TODAY_OBS_NODES, MSG_TIME, NEW_OBS_WITH_TIME_NODES, \
    MODIFIED_MEMORIES
from enumeration.memory_node_status import MemoryNodeStatus
from node.memory_wrap_node import MemoryWrapNode
from worker.memory_base_worker import MemoryBaseWorker


class ContraRepeatWorker(MemoryBaseWorker):
    def __init__(self, merge_obs_model, merge_obs_max_token, merge_obs_temperature, merge_obs_top_k, *args, **kwargs):
        super(ContraRepeatWorker, self).__init__(*args, **kwargs)
        self.merge_obs_model = merge_obs_model
        self.merge_obs_max_token = merge_obs_max_token
        self.merge_obs_temperature = merge_obs_temperature
        self.merge_obs_top_k = merge_obs_top_k

    def _run(self):
        # 合并当前的obs和今日的obs
        new_obs_nodes: List[MemoryWrapNode] = self.get_context(NEW_OBS_NODES)
        new_obs_with_time_nodes: List[MemoryWrapNode] = self.get_context(NEW_OBS_WITH_TIME_NODES)
        today_obs_nodes: List[MemoryWrapNode] = self.get_context(TODAY_OBS_NODES)
        all_obs_nodes: List[MemoryWrapNode] = []
        if new_obs_nodes:
            all_obs_nodes.extend(new_obs_nodes)
        if new_obs_with_time_nodes:
            all_obs_nodes.extend(new_obs_with_time_nodes)
        if today_obs_nodes:
            all_obs_nodes.extend(today_obs_nodes)
        if not all_obs_nodes:
            self.add_run_info("all_obs_nodes is empty!")
            return

        # gene prompt
        user_query_list = []
        all_obs_nodes = sorted(all_obs_nodes, key=lambda x: x.memory_node.metaData.get(MSG_TIME, ""), reverse=True)
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.memory_node.content}")
        merge_obs_message = self.prompt_to_msg(
            system_prompt=self.prompt_config.contra_repeat_system.format(num_obs=len(user_query_list)),
            few_shot=self.prompt_config.contra_repeat_few_shot,
            user_query=self.prompt_config.contra_repeat_user_query.format(user_query="\n".join(user_query_list)))
        self.logger.info(f"merge_obs_message={merge_obs_message}")

        # call LLM
        response_text = self.gene_client.call(messages=merge_obs_message,
                                              model_name=self.merge_obs_model,
                                              max_token=self.merge_obs_max_token,
                                              temperature=self.merge_obs_temperature,
                                              top_k=self.merge_obs_top_k)

        # return if empty
        if not response_text:
            self.add_run_info("contra repeat call llm failed!")
            return

        # parse text
        idx_merge_obs_list = ResponseTextParser(response_text).parse_v1("contra_repeat")
        if len(idx_merge_obs_list) <= 0:
            self.add_run_info("idx_merge_obs_list is empty!")
            return

        # add merged obs
        merge_obs_nodes: List[MemoryWrapNode] = []
        for obs_content_list in idx_merge_obs_list:
            if not obs_content_list:
                continue

            # [6, 逃课]
            if len(obs_content_list) != 2:
                self.logger.warning(f"obs_content_list={obs_content_list} is invalid!")
                continue

            idx, keep_flag = obs_content_list

            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            # 序号需要修正-1
            idx = int(idx) - 1
            if idx >= len(all_obs_nodes):
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            if keep_flag not in ["矛盾", "被包含", "无"]:
                self.logger.warning(f"keep_flag={keep_flag} is invalid!")
                continue

            node: MemoryWrapNode = all_obs_nodes[idx]
            if keep_flag != "无":
                node.memory_node.status = MemoryNodeStatus.EXPIRED.value
            merge_obs_nodes.append(node)
            self.logger.info(f"after contra repeat: {node.memory_node.content} {node.memory_node.status}")

        # save context
        self.set_context(MODIFIED_MEMORIES, merge_obs_nodes)
