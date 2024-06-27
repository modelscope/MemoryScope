from memory_base_worker import MemoryBaseWorker


class DummyWorker(MemoryBaseWorker):
    def _run(self):
        pass