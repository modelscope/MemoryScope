from typing import List

from memory_scope.constants.common_constants import RESULT, CHAT_MESSAGES
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class ReadMemory(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self, chat_messages: List[Message], his_msg_count: int = 0, contextual_msg_count: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.chat_messages: List[Message] = chat_messages
        self.his_msg_count: int = his_msg_count
        self.contextual_msg_count: int = contextual_msg_count

    def init_workflow(self):
        self.init_workers()

    def run_operation(self):
        max_count = 1 + max(self.his_msg_count, self.contextual_msg_count)
        self.context[CHAT_MESSAGES] = [x.copy() for x in self.chat_messages[-max_count:]]
        self.run_workflow()
        result = self.context.get(RESULT)
        self.context.clear()
        return result
