import time
from typing import List

from memory_scope.chat.global_context import G_CONTEXT
from memory_scope.constants.common_constants import CHAT_MESSAGES, RESULT, CHAT_KWARGS
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class WriteMemory(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self,
                 name: str,
                 description: str,
                 chat_messages: List[Message],
                 his_msg_count: int = 0,
                 message_lock=None,
                 interval_time: int = 60,
                 contextual_msg_count: int = 6,
                 **kwargs):

        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)

        self.chat_messages: List[Message] = chat_messages
        self.his_msg_count: int = his_msg_count
        self.message_lock = message_lock
        self.interval_time: int = interval_time
        self.contextual_msg_count: int = contextual_msg_count

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

    def init_workflow(self):
        self.init_workers()

    def run_operation(self, **kwargs):
        if self._operation_status_run:
            return

        self._operation_status_run = True
        self.context[CHAT_KWARGS] = kwargs
        not_memorized_size = self.not_memorized_size
        if not_memorized_size < self.contextual_msg_count:
            return

        max_count = not_memorized_size + self.his_msg_count
        self.context[CHAT_MESSAGES] = [x.copy(deep=True) for x in self.chat_messages[-max_count:]]
        self.run_workflow()
        result = self.context.get(RESULT)
        self.context.clear()
        self.set_memorized()
        self._operation_status_run = False

        return result

    def _loop_operation(self):
        while self._loop_switch:
            for _ in range(self.interval_time):
                if self._loop_switch:
                    time.sleep(1)
                else:
                    break
            if self._loop_switch:
                self.run_operation()

    def run_operation_backend(self):
        if not self._loop_switch:
            self._loop_switch = True
            return G_CONTEXT.thread_pool.submit(self._loop_operation)

    def stop_operation_backend(self):
        self._loop_switch = False
