from typing import List

from memory_scope.constants.common_constants import RESULT, CHAT_MESSAGES
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class ReadOperation(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self, chat_messages: List[Message], max_his_msg_count: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.chat_messages: List[Message] = chat_messages
        self.max_his_msg_count: int = max_his_msg_count

    def run_operation(self):
        max_count = 1 + self.max_his_msg_count
        self.context[CHAT_MESSAGES] = [x.copy() for x in self.chat_messages[-max_count:]]
        self.run_workflow()
        result = self.context.get(RESULT)
        self.context.clear()
        return result
