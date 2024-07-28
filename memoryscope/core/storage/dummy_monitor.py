from memoryscope.core.storage.base_monitor import BaseMonitor


class DummyMonitor(BaseMonitor):
    """
    DummyMonitor serves as a placeholder or mock class extending BaseMonitor,
    providing empty method bodies for 'add', 'add_token', and 'close' operations.
    This can be used for testing or in situations where a full monitor implementation is not required.
    """

    def add(self):
        """
        Placeholder for adding data to the monitor.
        This method currently does nothing.
        """
        pass

    def add_token(self):
        """
        Placeholder for adding a token to the monitored data.
        This method currently does nothing.
        """
        pass

    def close(self):
        """
        Placeholder for closing the monitor and performing any necessary cleanup.
        This method currently does nothing.
        """
        pass
