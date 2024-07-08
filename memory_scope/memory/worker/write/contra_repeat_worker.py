from typing import List

from memory_scope.constants.common_constants import NEW_OBS_NODES, NEW_OBS_WITH_TIME_NODES, MERGE_OBS_NODES
from memory_scope.constants.language_constants import NONE_WORD, CONTRADICTORY_WORD, INCLUDED_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.timer import timer


class ContraRepeatWorker(MemoryBaseWorker):

    @timer
    def retrieve_today_memory(self) -> List[MemoryNode]:
        if not self.chat_messages:
            self.logger.warning("chat_messages is empty!")
            return []

        message: Message = self.chat_messages[-1]
        dt_handler = DatetimeHandler(message.time_created)
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "dt": dt_handler.datetime_format(),
        }
        return self.memory_store.retrieve_memories(query=message.content, top_k=self.today_obs_top_k, filter_dict=filter_dict)

    def _run(self):
        all_obs_nodes: List[MemoryNode] = []

        new_obs_nodes: List[MemoryNode] = self.get_context(NEW_OBS_NODES)
        if new_obs_nodes:
            all_obs_nodes.extend(new_obs_nodes)
        new_obs_with_time_nodes: List[MemoryNode] = self.get_context(NEW_OBS_WITH_TIME_NODES)
        if new_obs_with_time_nodes:
            all_obs_nodes.extend(new_obs_with_time_nodes)
        if not all_obs_nodes:
            self.logger.info("all_obs_nodes is empty!")
            self.continue_run = False
            return

        today_obs_nodes: List[MemoryNode] = self.retrieve_today_memory()
        if today_obs_nodes:
            all_obs_nodes.extend(today_obs_nodes)
        all_obs_nodes = sorted(all_obs_nodes, key=lambda x: x.timestamp, reverse=True)[:self.contra_repeat_max_count]

        # build prompt
        user_query_list = []
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.content}")

        system_prompt = self.prompt_handler.contra_repeat_system.format(num_obs=len(user_query_list),
                                                                        user_name=self.user_id)
        few_shot = self.prompt_handler.contra_repeat_few_shot.format(user_name=self.user_id)
        user_query = self.prompt_handler.contra_repeat_user_query.format(user_query="\n".join(user_query_list),
                                                                         user_name=self.user_id)
        contra_repeat_message = self.prompt_to_msg(system_prompt=system_prompt,
                                                   few_shot=few_shot,
                                                   user_query=user_query)
        self.logger.info(f"contra_repeat_message={contra_repeat_message}")

        # call LLM
        response = self.generation_model.call(messages=contra_repeat_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response.status or not response.message.content:
            return
        response_text = response.message.content

        # parse text
        idx_merge_obs_list = ResponseTextParser(response_text).parse_v1(self.__class__.__name__)
        if len(idx_merge_obs_list) <= 0:
            self.add_run_info("idx_merge_obs_list is empty!")
            return

        # add merged obs
        merge_obs_nodes: List[MemoryNode] = []
        for obs_content_list in idx_merge_obs_list:
            if not obs_content_list:
                continue

            # [6, skipping classes]
            if len(obs_content_list) != 2:
                self.logger.warning(f"obs_content_list={obs_content_list} is invalid!")
                continue

            idx, keep_flag = obs_content_list

            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            # index number needs to be corrected to -1
            idx = int(idx) - 1
            if idx >= len(all_obs_nodes):
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            # judge flag
            if keep_flag not in self.get_language_value([NONE_WORD, CONTRADICTORY_WORD, INCLUDED_WORD]):
                self.logger.warning(f"keep_flag={keep_flag} is invalid!")
                continue

            node: MemoryNode = all_obs_nodes[idx]
            if keep_flag != self.get_language_value(NONE_WORD):
                node.memory_node.status = MemoryNodeStatus.EXPIRED.value
            merge_obs_nodes.append(node)

            # forbid keyword
            self.logger.info(f"contra_repeat stage: {node.content} {node.status}")

        # save context
        self.set_context(MERGE_OBS_NODES, merge_obs_nodes)
