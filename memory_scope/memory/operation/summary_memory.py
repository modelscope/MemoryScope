from memory_scope.constants.common_constants import RESULT, CHAT_KWARGS
from memory_scope.memory.operation.base_backend_operation import BaseBackendOperation
from memory_scope.memory.operation.base_operation import OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow


class SummaryMemory(BaseWorkflow, BaseBackendOperation):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        BaseBackendOperation.__init__(self, **kwargs)

    def init_workflow(self, **kwargs):
        self.init_workers(is_backend=True, **kwargs)

    def _run_operation(self, **kwargs):
        self.context[CHAT_KWARGS] = kwargs
        self.run_workflow()
        result = self.context.get(RESULT)
        self.context.clear()
        return result
