from memory_scope.memory.worker.base_worker import BaseWorker


class DummyWorker(BaseWorker):
    def _run(self):
        self.logger.info("enter dummy worker!")
