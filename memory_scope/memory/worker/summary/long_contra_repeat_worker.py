from typing import List, Dict

from memory_scope.constants.common_constants import (
    MODIFIED_MEMORIES, NOT_UPDATED_NODES,
)
from memory_scope.constants.language_constants import NONE_WORD, INCLUDED_WORD, CONTRADICTORY_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class LongContraRepeatWorker(MemoryBaseWorker):

    async def retrieve_similar_content(self, node: MemoryNode) -> (MemoryNode, List[MemoryNode]):
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value]
        }
        retrieve_nodes = await self.vector_store.async_retrieve(query=node.content,
                                                                top_k=self.long_contra_repeat_top_k,
                                                                filter_dict=filter_dict)
        return node, [n for n in retrieve_nodes if n.score_similar >= self.long_contra_repeat_threshold]

    def _run(self):
        not_updated_nodes: List[MemoryNode] = self.get_context(NOT_UPDATED_NODES)
        for node in not_updated_nodes:
            self.submit_async_task(fn=self.retrieve_similar_content, node=node)

        obs_node_dict: Dict[str, MemoryNode] = {}
        for origin_node, retrieve_nodes in self.gather_async_result():
            if not retrieve_nodes:
                continue
            obs_node_dict[origin_node.memory_id] = origin_node
            for node in retrieve_nodes:
                if node.memory_id in obs_node_dict:
                    continue
                obs_node_dict[node.memory_id] = node
        all_obs_nodes: List[MemoryNode] = sorted(obs_node_dict.values(), key=lambda x: x.timestamp, reverse=True)

        if not all_obs_nodes:
            self.logger.warning("all_obs_nodes is empty, stop.")
            return

        # gene prompt
        user_query_list = []
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.content}")
        system_prompt = self.prompt_handler.long_contra_repeat_system.format(num_obs=len(user_query_list),
                                                                             user_name=self.target_name)
        few_shot = self.prompt_handler.long_contra_repeat_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.long_contra_repeat_user_query.format(user_query="\n".join(user_query_list))

        long_contra_repeat_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"long_contra_repeat_message={long_contra_repeat_message}")

        # call LLM
        response = self.generation_model.call(messages=long_contra_repeat_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response:
            return

        # parse text
        idx_merge_obs_list = ResponseTextParser(response.message.content).parse_v1("contra_repeat")
        if len(idx_merge_obs_list) <= 0:
            self.add_run_info("idx_merge_obs_list is empty!")
            return

        # add merged obs
        merge_obs_nodes: List[MemoryNode] = []
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

            if keep_flag not in self.get_language_value([CONTRADICTORY_WORD, INCLUDED_WORD, NONE_WORD]):
                self.logger.warning(f"keep_flag={keep_flag} is invalid!")
                continue

            node: MemoryNode = all_obs_nodes[idx]
            if keep_flag != self.get_language_value(NONE_WORD):
                node.status = MemoryNodeStatus.EXPIRED.value
            merge_obs_nodes.append(node)
            self.logger.info(f"after contra repeat: {node.content} {node.status}")

        # save context
        self.set_context(MODIFIED_MEMORIES, merge_obs_nodes)
