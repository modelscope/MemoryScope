from typing import List

from memory_scope.constants.common_constants import NEW_OBS_NODES, TIME_INFER
from memory_scope.constants.language_constants import REPEATED_WORD, NONE_WORD, COLON_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class GetObservationWorker(MemoryBaseWorker):
    FILE_PATH: str = __file__
    OBS_STORE_KEY: str = NEW_OBS_NODES

    def add_observation(self, message: Message, time_infer: str, obs_content: str, keywords: str):
        dt_handler = DatetimeHandler(dt=message.time_created)

        # buidl meta data
        meta_data = {
            MemoryTypeEnum.CONVERSATION.value: message.content,
            TIME_INFER: time_infer,
            "keywords": keywords,
            **dt_handler.dt_info_dict,
        }

        if time_infer:
            dt_info_dict = DatetimeHandler.extract_date_parts(input_string=time_infer)
            meta_data.update({f"event_{k}": str(v) for k, v in dt_info_dict.items()})

        return MemoryNode(user_name=self.user_name,
                          target_name=self.target_name,
                          meta_data=meta_data,
                          content=obs_content,
                          memory_type=MemoryTypeEnum.OBSERVATION.value,
                          status=MemoryNodeStatus.NEW.value,
                          timestamp=message.time_created,
                          obs_reflected=False,
                          obs_updated=False)

    def filter_messages(self) -> List[Message]:
        filter_messages = []
        for msg in self.chat_messages:
            if not DatetimeHandler.has_time_word(query=msg.content):
                filter_messages.append(msg)
        return filter_messages

    def build_message(self, filter_messages: List[Message]) -> List[Message]:
        user_query_list = []
        for i, msg in enumerate(filter_messages):
            user_query_list.append(f"{i} {self.target_name}{self.get_language_value(COLON_WORD)}{msg.content}")

        system_prompt = self.prompt_handler.get_observation_system.format(num_obs=len(user_query_list),
                                                                          user_name=self.target_name)
        few_shot = self.prompt_handler.get_observation_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.get_observation_user_query.format(user_query="\n".join(user_query_list),
                                                                           user_name=self.target_name)

        obtain_obs_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")
        return obtain_obs_message

    def _run(self):
        filter_messages = self.filter_messages()
        if not filter_messages:
            self.logger.warning("get obs filter_messages is empty!")
            return

        obtain_obs_message = self.build_message(filter_messages)

        # call LLM
        response = self.generation_model.call(messages=obtain_obs_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response.status or not response.message.content:
            return
        response_text = response.message.content

        # parse text
        idx_obs_list = ResponseTextParser(response_text).parse_v1(self.__class__.__name__)
        if len(idx_obs_list) <= 0:
            self.logger.warning("idx_obs_list is empty!")
            return

        # gene new obs nodes
        new_obs_nodes: List[MemoryNode] = []
        for obs_content_list in idx_obs_list:
            if not obs_content_list:
                continue

            # [1, In June 2022, the user will travel to Hangzhou for tourism, tourism]
            if len(obs_content_list) != 4:
                self.logger.warning(f"obs_content_list={obs_content_list} is invalid!")
                continue

            idx, time_infer, obs_content, keywords = obs_content_list

            if obs_content in self.get_language_value([NONE_WORD, REPEATED_WORD]):
                continue

            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            if time_infer == self.get_language_value(NONE_WORD):
                time_infer = ""

            # index number needs to be corrected to -1
            idx = int(idx) - 1
            if idx >= len(filter_messages):
                self.logger.warning(f"idx={idx} is invalid! filter_messages.size={len(filter_messages)}")
                continue

            new_obs_nodes.append(self.add_observation(message=filter_messages[idx],
                                                      time_infer=time_infer,
                                                      obs_content=obs_content,
                                                      keywords=keywords))

        self.set_memories(self.OBS_STORE_KEY, new_obs_nodes)
