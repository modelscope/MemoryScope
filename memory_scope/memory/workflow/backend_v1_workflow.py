import time

from memory_scope.constants.common_constants import RESULT, CHAT_MESSAGES
from memory_scope.memory.workflow.base_workflow import BaseWorkflow


class BackendV1Workflow(BaseWorkflow):

    def __init__(self, interval_time: int, min_count: int, **kwargs):
        super().__init__(**kwargs)
        self.interval_time: int = interval_time
        self.min_count: int = min_count

    @property
    def not_memorized_size(self):
        return sum([not x.memorized for x in self.chat_messages])

    def set_memorized(self):
        for msg in self.chat_messages:
            msg.memorized = True

    def _loop(self):
        while self.loop_switch:
            time.sleep(self.interval_time)
            if self.not_memorized_size < self.min_count:
                continue

            self.context[CHAT_MESSAGES] = self.chat_messages
            self.__call__()
            self.context.clear()
            self.set_memorized()

    def start_loop_run(self):
        if not self.loop_switch:
            self.loop_switch = True
            return GLOBAL_CONTEXT.thread_pool.submit(self._thread_loop)

    def run_workflow(self):
        self.context[CHAT_MESSAGES] = self.chat_messages
        self.__call__()
        result = self.context.get(RESULT)
        self.context.clear()
        return result
