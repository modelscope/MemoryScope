from memory_scope.constants.common_constants import RESULT
from memory_scope.memory.worker.base_worker import BaseWorker


class DummyWorker(BaseWorker):
    def _run(self):
        self.set_context(RESULT, ["test 123"])
        self.logger.info("enter dummy worker!")
