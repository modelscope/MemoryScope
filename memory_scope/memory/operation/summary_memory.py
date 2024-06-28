import time

from memory_scope.chat.global_context import G_CONTEXT
from memory_scope.constants.common_constants import RESULT, CHAT_KWARGS
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow


class SummaryMemory(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self,
                 name: str,
                 description: str,
                 interval_time: int = 300,
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)

        self.interval_time: int = interval_time

        self._operation_status_run: bool = False
        self._loop_switch: bool = False
        self._run_thread = None

    def init_workflow(self):
        self.init_workers()

    def run_operation(self, **kwargs):
        if self._operation_status_run:
            return

        self._operation_status_run = True
        self.context[CHAT_KWARGS] = kwargs
        self.run_workflow()
        result = self.context.get(RESULT)
        self.context.clear()
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
            self._run_thread = G_CONTEXT.thread_pool.submit(self._loop_operation)

    def stop_operation_backend(self):
        self._loop_switch = False
