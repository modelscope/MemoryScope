from typing import List

from memory_scope.constants.common_constants import NOT_REFLECTED_NODES, INSIGHT_NODES
from memory_scope.constants.language_constants import COMMA_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class GetReflectionSubjectWorker(MemoryBaseWorker):
    FILE_PATH: str = __file__

    def new_insight_node(self, insight_key: str) -> MemoryNode:
        dt_handler = DatetimeHandler()
        meta_data = {k: str(v) for k, v in dt_handler.dt_info_dict.items()}

        return MemoryNode(user_name=self.user_name,
                          target_name=self.target_name,
                          meta_data=meta_data,
                          key=insight_key,
                          memory_type=MemoryTypeEnum.INSIGHT.value,
                          status=MemoryNodeStatus.NEW.value)

    def _run(self):
        not_reflected_nodes: List[MemoryNode] = self.get_memories(NOT_REFLECTED_NODES)
        insight_nodes: List[MemoryNode] = self.get_memories(INSIGHT_NODES)

        # count
        not_reflected_count = len(not_reflected_nodes)
        if not_reflected_count <= self.reflect_obs_cnt_threshold:
            self.logger.info(f"not_reflected_count={not_reflected_count} is not enough, stop.")
            self.continue_run = False
            return

        # get profile_keys
        exist_keys: List[str] = [n.key for n in insight_nodes]
        self.logger.info(f"exist_keys={exist_keys}")

        # gen reflect prompt
        user_query_list = [n.content for n in not_reflected_nodes]
        system_prompt = self.prompt_handler.get_reflection_subject_system.format(
            user_name=self.target_name,
            num_questions=self.reflect_num_questions)
        few_shot = self.prompt_handler.get_reflection_subject_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.get_reflection_subject_user_query.format(
            user_name=self.target_name,
            exist_keys=self.get_language_value(COMMA_WORD).join(exist_keys),
            user_query="\n".join(user_query_list))

        reflect_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"reflect_message={reflect_message}")

        # # call LLM
        response = self.generation_model.call(messages=reflect_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response.status or not response.message.content:
            return

        # parse text & save
        new_insight_keys = ResponseTextParser(response.message.content).parse_v2(self.__class__.__name__)
        if new_insight_keys:
            for insight_key in new_insight_keys:
                insight_nodes.append(self.new_insight_node(insight_key))

        for node in not_reflected_nodes:
            node.obs_reflected = True
