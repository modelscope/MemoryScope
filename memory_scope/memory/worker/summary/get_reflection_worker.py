from typing import List

from memory_scope.constants.common_constants import NOT_REFLECTED_NODES, INSIGHT_NODES
from memory_scope.constants.language_constants import COMMA_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.timer import timer
from memory_scope.utils.tool_functions import prompt_to_msg


class GetReflectionWorker(MemoryBaseWorker):
    @timer
    def retrieve_not_reflected_memory(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value],
            "obs_reflected": False,
        }
        return self.vector_store.retrieve(query=query, top_k=self.retrieve_not_reflected_top_k, filter_dict=filter_dict)

    @timer
    def retrieve_insight_memory(self, query: str) -> List[MemoryNode]:
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": MemoryTypeEnum.INSIGHT.value,
        }
        return self.vector_store.retrieve(query=query, top_k=self.retrieve_insight_top_k, filter_dict=filter_dict)

    def new_insight_node(self, insight_key: str) -> MemoryNode:
        dt_handler = DatetimeHandler()
        meta_data = {k: str(v) for k, v in dt_handler.dt_info_dict.items()}

        return MemoryNode(user_name=self.user_name,
                          target_name=self.target_name,
                          meta_data=meta_data,
                          key=insight_key,
                          memory_type=MemoryTypeEnum.INSIGHT.value,
                          status=MemoryNodeStatus.ACTIVE.value)

    def _run(self):
        not_reflected_nodes: List[MemoryNode] = []
        insight_nodes: List[MemoryNode] = []

        fn_list = [self.retrieve_not_reflected_memory, self.retrieve_insight_memory]
        for nodes in self.async_run(fn_list=fn_list, query="_"):
            if not nodes:
                continue
            for node in nodes:
                if node.memory_type == MemoryTypeEnum.INSIGHT.value:
                    insight_nodes.append(node)
                else:
                    not_reflected_nodes.append(node)

        self.set_context(INSIGHT_NODES, insight_nodes)

        # count
        not_reflected_count = len(not_reflected_nodes)
        if not_reflected_count <= self.reflect_obs_cnt_threshold:
            self.logger.info(f"not_reflected_count={not_reflected_count} is not enough, stop.")
            return

        # save context
        self.set_context(NOT_REFLECTED_NODES, not_reflected_nodes)

        # get profile_keys
        exist_keys: List[str] = [n.key for n in insight_nodes]
        self.logger.info(f"exist_keys={exist_keys}")

        # gen reflect prompt
        user_query_list = [n.content for n in not_reflected_nodes]
        system_prompt = self.prompt_handler.get_reflect_system.format(user_name=self.target_name,
                                                                      num_questions=self.reflect_num_questions)
        few_shot = self.prompt_handler.get_reflect_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.get_reflect_user_query.format(
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
        new_insight_keys = ResponseTextParser(response.message.content).parse_v2("get_reflection")
        if new_insight_keys:
            for insight_key in new_insight_keys:
                insight_nodes.append(self.new_insight_node(insight_key))
