import datetime
from typing import List

from memory_scope.chat.base_memory_chat import BaseMemoryChat
from memory_scope.chat.global_context import GLOBAL_CONTEXT
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.models.base_model import BaseModel
from memory_scope.node.message import Message
from memory_scope.prompts.prompt_cn import SYSTEM_PROMPT, MEMORY_PROMPT


class MemoryChat(BaseMemoryChat):
    """
    TODO add agent
    """

    def __init__(self,
                 generation_model: str,
                 history_msg_count: int,
                 **kwargs):
        super().__init__(**kwargs)
        self.model: BaseModel = GLOBAL_CONTEXT.model_dict[generation_model]
        self.history_msg_count: int = history_msg_count

        self.memory_service.start_summary_short_backend()
        self.memory_service.start_summary_long_backend()

        self.history_message_list: List[Message] = []

    @staticmethod
    def get_system_prompt(related_memories: List[str], time_created: int) -> Message:
        system_prompt = SYSTEM_PROMPT
        if related_memories:
            system_prompt = "\n".join([SYSTEM_PROMPT, MEMORY_PROMPT] + related_memories)
        return Message(role=MessageRoleEnum.SYSTEM, content=system_prompt.strip(), time_created=time_created)

    def chat_with_memory(self, query: str):
        query = query.strip()
        if not query:
            return
        time_created = int(datetime.datetime.now().timestamp())
        new_message: Message = Message(role=MessageRoleEnum.USER, content=query, time_created=time_created)
        related_memories: List[str] = self.memory_service.retrieve(message=new_message)
        system_message = self.get_system_prompt(related_memories, time_created)
        self.history_message_list.append(new_message)
        self.history_message_list = self.history_message_list[-self.history_msg_count:]
        all_messages = [system_message] + self.history_message_list
        return self.model.call(messages=all_messages)

    def chat_with_memory_stream(self):
        raise NotImplementedError
