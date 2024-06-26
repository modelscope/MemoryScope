import time

from memory_scope.chat_v2.global_context import G_CONTEXT
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow


class SummaryMemory(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self, interval_time: int = 300, **kwargs):
        super().__init__(**kwargs)

        self.interval_time: int = interval_time

        self._operation_status_run: bool = False
        self._loop_switch: bool = False

    def init_workflow(self):
        self.init_workers()

    def run_operation(self):
        if self._operation_status_run:
            return

        self._operation_status_run = True
        self.run_workflow()
        self.context.clear()
        self._operation_status_run = False

    def _loop_operation(self):
        while self._loop_switch:
            time.sleep(self.interval_time)
            self.run_operation()

    def run_operation_backend(self):
        if not self._loop_switch:
            self._loop_switch = True
            return G_CONTEXT.thread_pool.submit(self._loop_operation)
