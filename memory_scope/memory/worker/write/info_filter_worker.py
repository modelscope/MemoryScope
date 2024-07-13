from typing import List

from memory_scope.constants.language_constants import COLON_WORD
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.message import Message
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class InfoFilterWorker(MemoryBaseWorker):
    """
    This worker filters and modifies the chat message history (`self.chat_messages`) by retaining only the messages 
    that include significant information. It then constructs a prompt from these filtered messages, utilizes an AI 
    model to process this prompt, parses the AI's generated response to allocate scores, and ultimately retains 
    messages in `self.chat_messages` based on these assigned scores.
    """
    FILE_PATH: str = __file__

    def _run(self):
        """
        Filters user messages in the chat, generates a prompt incorporating these messages, 
        utilizes an LLM to process the prompt, parses the LLM's response to score each message, 
        and updates `self.chat_messages` to only include messages with designated scores.
        
        This method executes the following steps:
        1. Filters out non-user messages and truncates long messages.
        2. Constructs a prompt with user messages for LLM input.
        3. Calls the LLM model with the constructed prompt.
        4. Parses the LLM's response to extract message scores.
        5. Retains messages in `self.chat_messages` based on their scores.
        """
        # filter user msg
        info_messages: List[Message] = []
        for msg in self.chat_messages:
            if msg.memorized:
                continue

            # TODO: add memory for assistant
            if msg.role != MessageRoleEnum.USER.value:
                continue

            if len(msg.content) >= self.info_filter_msg_max_size:
                half_size = int(self.info_filter_msg_max_size * 0.5 + 0.5)
                msg.content = msg.content[: half_size] + msg.content[-half_size:]
            info_messages.append(msg)

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
        for info_score in info_score_list:
            if not info_score:
                continue

            if len(info_score) != 2:
                self.logger.warning(f"info_score={info_score} is invalid!")
                continue

            idx, score = info_score

            idx = int(idx) - 1
            if idx >= len(info_messages):
                self.logger.warning(f"idx={idx} is invalid! info_messages.size={len(info_messages)}")
                continue
            message = info_messages[idx]

            if score in self.preserved_scores:
                message.meta_data["info_score"] = score
                filtered_messages.append(message)
                self.logger.info(f"info filter stage: keep {message.content}")

        self.chat_messages = filtered_messages
