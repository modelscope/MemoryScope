from typing import List

from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.scheme.message import Message


class ReadMessage(BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self,
                 name: str,
                 description: str,
                 chat_messages: List[Message],
                 contextual_msg_count: int,  # for the current context dialogue
                 **kwargs):
        super().__init__(name=name, description=description, **kwargs)
        self.chat_messages: List[Message] = chat_messages
        self.contextual_msg_count: int = contextual_msg_count

    def run_operation(self, **kwargs):
        return self.chat_messages[-self.contextual_msg_count:]
