from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow


class ClearMemory(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self,
                 name: str,
                 description: str,
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)

    def init_workflow(self, **kwargs):
        self.init_workers(**kwargs)

    def run_operation(self, **kwargs):
        self.context.clear()
        self.run_workflow()
