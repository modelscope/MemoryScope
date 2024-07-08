import time
from abc import abstractmethod

from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger


class BaseBackendOperation(BaseOperation):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self, interval_time: int, **kwargs):
        super(BaseBackendOperation, self).__init__(**kwargs)

        self.interval_time: int = interval_time

        self._operation_status_run: bool = False
        self._loop_switch: bool = False
        self._run_thread = None

        self.logger = Logger.get_logger()

    @abstractmethod
    def _run_operation(self, **kwargs):
        raise NotImplementedError

    def run_operation(self, **kwargs):
        if self._operation_status_run:
            return

        self._operation_status_run = True
        result = None
        try:
            result = self._run_operation(**kwargs)
        except Exception as e:
            self.logger.exception(f"{self.name} encounter exception. args={e.args}")

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
