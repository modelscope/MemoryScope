from typing import List

from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.constants.common_constants import (
    NEW_OBS_NODES,
    MSG_TIME,
    MODIFIED_MEMORIES,
)
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.utils.tool_functions import prompt_to_msg
from memory_scope.constants.language_constants import NONE_WORD, INCLUDED_WORD, CONTRADICTORY_WORD


class LongContraRepeatWorker(MemoryBaseWorker):

    def _run(self):
        # 合并当前的obs和今日的obs
        new_obs_nodes: List[MemoryNode] = self.get_context(NEW_OBS_NODES)
        all_obs_nodes: List[MemoryNode] = []
        for new_obs_node in new_obs_nodes:
            text = new_obs_node.content
            related_nodes = self.vector_store.similar_search(
                text=text,
                size=self.es_contra_repeat_similar_top_k,
                exact_filters={
                    "user_name": self.user_name,
                    "target_name": self.target_name,
                    "status": MemoryNodeStatus.ACTIVE.value,
                    "memory_type": [
                        MemoryTypeEnum.OBSERVATION.value,
                        MemoryTypeEnum.OBS_CUSTOMIZED.value,
                    ],
                },
            )

            has_match = False
            for related_node in related_nodes:
                if related_node.score_similar < self.long_contra_repeat_threshold:
                    continue
                else:
                    has_match = True
                    all_obs_nodes.append(related_node)
            if has_match:
                all_obs_nodes.append(new_obs_node)

        if not all_obs_nodes:
            self.add_run_info("all_obs_nodes is empty!")
            return

        # gene prompt
        user_query_list = []
        all_obs_nodes = sorted(
            all_obs_nodes,
            key=lambda x: x.meta_data.get(MSG_TIME, ""),
            reverse=True,
        )
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.content}")
        merge_obs_message = prompt_to_msg(
            system_prompt=self.prompt_handler.system_prompt.format(
                num_obs=len(user_query_list)
            ),
            few_shot=self.prompt_handler.few_shot_prompt,
            user_query=self.prompt_handler.user_query_prompt.format(
                user_query="\n".join(user_query_list)
            ),
        )
        self.logger.info(f"merge_obs_message={merge_obs_message}")

        # call LLM
        response = self.generation_model.call(
            messages=merge_obs_message,
            model_name=self.merge_obs_model,
            max_token=self.merge_obs_max_token,
            temperature=self.merge_obs_temperature,
            top_k=self.merge_obs_top_k,
        )

        # return if empty
        if not response:
            self.add_run_info("contra repeat call llm failed!")
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

            long_contra_repeat_keep_flag = [
                self.get_language_value(CONTRADICTORY_WORD),
                self.get_language_value(INCLUDED_WORD),
                self.get_language_value(NONE_WORD),
            ]
            
            if keep_flag not in long_contra_repeat_keep_flag.values():
                self.logger.warning(f"keep_flag={keep_flag} is invalid!")
                continue

            node: MemoryNode = all_obs_nodes[idx]
            if keep_flag != self.get_language_value(NONE_WORD):
                node.status = MemoryNodeStatus.EXPIRED.value
            merge_obs_nodes.append(node)
            self.logger.info(f"after contra repeat: {node.content} {node.status}")

        # save context
        self.set_context(MODIFIED_MEMORIES, merge_obs_nodes)
