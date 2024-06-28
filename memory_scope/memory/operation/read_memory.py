from typing import List

from memory_scope.constants.common_constants import RESULT, CHAT_MESSAGES, CHAT_KWARGS
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class ReadMemory(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self,
                 name: str,
                 description: str,
                 chat_messages: List[Message],
                 his_msg_count: int = 0,  # supplement to the current query
                 contextual_msg_count: int = 0,  # for the current context dialogue
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)
        self.chat_messages: List[Message] = chat_messages
        self.his_msg_count: int = his_msg_count
        self.contextual_msg_count: int = contextual_msg_count

    def init_workflow(self):
        self.init_workers()

    def run_operation(self, **kwargs):
        max_count = 1 + max(self.his_msg_count, self.contextual_msg_count)
        self.context[CHAT_MESSAGES] = [x.copy(deep=True) for x in self.chat_messages[-max_count:]]
        self.context[CHAT_KWARGS] = kwargs
        self.run_workflow()
        result = self.context.get(RESULT)
        self.context.clear()
        return result
