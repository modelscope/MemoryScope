from datetime import datetime
from typing import List

from memory_scope.constants.common_constants import NEW_OBS_NODES, TIME_INFER
from memory_scope.constants.language_constants import DATATIME_WORD_LIST, REPEATED_WORD, NONE_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class GetObservationWorker(MemoryBaseWorker):
    def add_observation(self, message: Message, time_infer: str, obs_content: str, keywords: str):
        created_dt: datetime = datetime.fromtimestamp(float(message.time_created))
        dt_handler = DatetimeHandler(dt=created_dt)

        # 组合meta_data
        meta_data = {
            MemoryTypeEnum.CONVERSATION.value: message.content,
            TIME_INFER: time_infer,
            **{f"msg_{k}": str(v) for k, v in dt_handler.dt_info_dict.items()},
        }

        if time_infer:
            dt_infer_handler = DatetimeHandler(dt=time_infer)
            meta_data.update({f"event_{k}": str(v) for k, v in dt_infer_handler.dt_info_dict.items()})

        node = MemoryNode(user_id=self.user_id,
                          meta_data=meta_data,
                          content=obs_content,
                          memoryType=MemoryTypeEnum.OBSERVATION.value,
                          status=MemoryNodeStatus.ACTIVE.value,
                          timestamp=message.time_created,
                          obs_dt=dt_handler.datetime_format(),
                          obs_reflected=False,
                          obs_profile_updated=False,
                          keywords=keywords)
        node.gen_memory_id()
        return node

    def build_prompt(self):
        # build prompt
        user_query_list = []
        i = 1
        for msg in self.chat_messages:
            match = False
            for time_keyword in self.get_language_value(DATATIME_WORD_LIST):
                if time_keyword in msg.content:
                    match = True
                    break
            if not match:
                user_query_list.append(f"{i} {self.user_id}：{msg.content}")
                i += 1

        if not user_query_list:
            self.logger.warning(f"get obs user_query_list={user_query_list} is empty")
            return

        system_prompt = self.prompt_handler.get_observation_system.format(num_obs=len(user_query_list),
                                                                          user_name=self.user_id)
        few_shot = self.prompt_config.get_observation_few_shot.format(self.user_id)
        user_query = self.prompt_config.get_observation_user_query.format(user_query="\n".join(user_query_list),
                                                                          user_name=self.user_id)

        obtain_obs_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")
        return obtain_obs_message

    def _run(self):
        obtain_obs_message = self.build_prompt()

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

            # index number needs to be corrected to -1
            idx = int(idx) - 1
            if idx >= len(self.messages):
                self.logger.warning(f"idx={idx} is invalid! messages.size={len(self.messages)}")
                continue

            new_obs_nodes.append(self.add_observation(message=self.messages[idx],
                                                      time_infer=time_infer,
                                                      obs_content=obs_content,
                                                      keywords=keywords))

        # save context
        self.set_context(NEW_OBS_NODES, new_obs_nodes)
