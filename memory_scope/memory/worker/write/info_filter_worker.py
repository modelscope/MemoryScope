from typing import List

from memory_scope.constants.language_constants import COLON_WORD
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.message import Message
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class InfoFilterWorker(MemoryBaseWorker):
    """
    This worker will filter and modify `self.chat_messages`, preserving only the messages that contain important information.
    """
    FILE_PATH: str = __file__

    def _run(self):
        # filter user msg
        info_messages: List[Message] = []
        for msg in self.chat_messages:
            # TODO: add memory for assistant
            if msg.role != MessageRoleEnum.USER.value:
                continue
            if len(msg.content) >= self.info_filter_msg_max_size:
                half_size = int(self.info_filter_msg_max_size * 0.5 + 0.5)
                msg.content = msg.content[: half_size] + msg.content[-half_size:]
            info_messages.append(msg)

        self.logger.warning(info_messages)

        if not info_messages:
            self.logger.warning("info_messages is empty!")
            self.continue_run = False
            return

        # generate prompt
        user_query_list = []
        for i, msg in enumerate(info_messages):
            user_query_list.append(f"{i + 1} {self.target_name}{self.get_language_value(COLON_WORD)}{msg.content}")
        self.logger.warning(self.prompt_handler.prompt_dict)
        system_prompt = self.prompt_handler.info_filter_system.format(batch_size=len(info_messages),
                                                                      user_name=self.target_name)
        few_shot = self.prompt_handler.info_filter_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.info_filter_user_query.format(user_query="\n".join(user_query_list),
                                                                       user_name=self.target_name)
        info_filter_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"info_filter_message={info_filter_message}")

        # call llm
        response = self.generation_model.call(messages=info_filter_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response.status or not response.message.content:
            self.continue_run = False
            return
        response_text = response.message.content

        # parse text
        info_score_list = ResponseTextParser(response_text).parse_v1(self.__class__.__name__)
        if len(info_score_list) != len(info_messages):
            self.logger.warning(f"score_size != messages_size, {len(info_score_list)} vs {len(info_messages)}")
            self.continue_run = False
            return

        # filter messages
        filtered_messages: List[Message] = []
        for msg, info_score in zip(info_messages, info_score_list):
            if not info_score:
                continue

            score = info_score[0]
            if score in ("3",):
                msg.meta_data["info_score"] = score
                filtered_messages.append(msg)
        self.chat_messages = filtered_messages
