from memory_scope.constants.common_constants import RESULT, WORKFLOW_NAME
from memory_scope.memory.worker.base_worker import BaseWorker


class DummyWorker(BaseWorker):
    def _run(self):
        workflow_name = self.get_context(WORKFLOW_NAME)
        self.logger.info(f"enter workflow={workflow_name}.dummy_worker!")
        self.set_context(RESULT, f"test {workflow_name}")
