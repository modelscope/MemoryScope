import time
from typing import List

from memory_scope.chat_v2.global_context import G_CONTEXT
from memory_scope.constants.common_constants import CHAT_MESSAGES
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class WriteOperation(BaseOperation, BaseWorkflow):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self,
                 chat_messages: List[Message],
                 max_his_msg_count: int = 0,
                 message_lock=None,
                 interval_time: int = 60,
                 min_count: int = 5,
                 **kwargs):
        super().__init__(**kwargs)

        self.chat_messages: List[Message] = chat_messages
        self.max_his_msg_count: int = max_his_msg_count
        self.message_lock = message_lock
        self.interval_time: int = interval_time
        self.min_count: int = min_count

        self._operation_status_run: bool = False
        self._loop_switch: bool = False

    @property
    def not_memorized_size(self):
        return sum([not x.memorized for x in self.chat_messages])

    def set_memorized(self):
        if self.message_lock:
            with self.message_lock:
                for msg in self.chat_messages:
                    msg.memorized = True

    def run_operation(self):
        if self._operation_status_run:
            return

        self._operation_status_run = True
        not_memorized_size = self.not_memorized_size
        if not_memorized_size < self.min_count:
            return

        max_count = not_memorized_size + self.max_his_msg_count
        self.context[CHAT_MESSAGES] = [x.copy() for x in self.chat_messages[-max_count:]]
        self.run_workflow()
        self.context.clear()
        self.set_memorized()
        self._operation_status_run = False

    def _loop_operation(self):
        while self._loop_switch:
            time.sleep(self.interval_time)
            self.run_operation()

    def run_operation_backend(self):
        if not self._loop_switch:
            self._loop_switch = True
            return G_CONTEXT.thread_pool.submit(self._loop_operation)
