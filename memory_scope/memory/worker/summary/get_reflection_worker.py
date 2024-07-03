from typing import List

from memory_scope.constants.common_constants import NOT_REFLECTED_NODES
from memory_scope.constants.language_constants import COMMA_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.timer import timer
from memory_scope.utils.tool_functions import prompt_to_msg


class GetReflectionWorker(MemoryBaseWorker):
    @timer
    def retrieve_not_reflected_memory(self) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_reflected": False,
        }
        return self.vector_store.retrieve(query=" ", top_k=self.retrieve_top_k, filter_dict=filter_dict)

    def _run(self):
        not_reflected_nodes: List[MemoryNode] = self.retrieve_not_reflected_memory()

        # count
        not_reflected_count = len(not_reflected_nodes)
        if not_reflected_count <= self.reflect_obs_cnt_threshold:
            self.logger.info(f"not_reflected_count={not_reflected_count} is not enough, stop.")
            return

        # save context
        self.set_context(NOT_REFLECTED_NODES, not_reflected_nodes)

        # get profile_keys
        exist_keys: List[str] = []
        profile_keys: List[str] = list(self.user_profile_dict.keys())
        exist_keys.extend(profile_keys)
        self.logger.info(f"profile_keys={profile_keys}")

        # get insight_keys
        insight_nodes: List[MemoryNode] = self.get_context(INSIGHT_NODES)
        if insight_nodes:
            insight_keys = [
                n.insight_key for n in insight_nodes
            ]
            insight_keys = [x.strip() for x in insight_keys if x]
            exist_keys.extend(insight_keys)
            self.logger.info(f"insight_keys={insight_keys}")

        # gen reflect prompt
        user_query_list = [n.content for n in not_reflected_merge_nodes]
        reflect_message = prompt_to_msg(
            system_prompt=self.prompt_handler.system_prompt.format(
                num_questions=self.reflect_num_questions
            ),
            few_shot=self.prompt_handler.few_shot_prompt,
            user_query=self.prompt_handler.user_query_prompt.format(
                exist_keys=self.get_language_value(COMMA_WORD).join(exist_keys), user_query="\n".join(user_query_list)
            ),
        )
        self.logger.info(f"reflect_message={reflect_message}")

        # # call LLM
        response = self.generation_model.call(
            messages=reflect_message,
            model_name=self.reflect_obs_model,
            max_token=self.reflect_obs_max_token,
            temperature=self.reflect_obs_temperature,
            top_k=self.reflect_obs_top_k,
        )

        # return if empty
        if not response:
            self.add_run_info("reflect_obs_questions call llm failed!")
            return

        # parse text & save
        new_insight_keys = ResponseTextParser(response.message.content).parse_v2(
            "get_insight_keys"
        )
        if new_insight_keys:
            self.set_context(NEW_INSIGHT_KEYS, new_insight_keys)
