from memory_scope.storage.base_monitor import BaseMonitor


class DummyMonitor(BaseMonitor):
    def add(self):
        pass

    def add_token(self):
        pass

    def flush(self):
        pass
