from abc import ABCMeta, abstractmethod


class BaseMonitor(metaclass=ABCMeta):
    """
    An abstract base class defining the interface for monitor classes.
    Subclasses should implement the methods defined here to provide concrete monitoring behavior.
    """

    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def add(self):
        """
        Abstract method to add data or events to the monitor.
        This method should be implemented by subclasses to define how data is added into the monitoring system.

        :return: None
        """

    @abstractmethod
    def add_token(self):
        """
        Abstract method to add a token or a specific type of identifier to the monitor.
        Subclasses should implement this to specify how tokens are managed within the monitoring context.

        :return: None
        """

    def flush(self):
        """
        Method to flush any buffered data in the monitor.
        Intended to ensure that all pending recorded data is processed or written out.

        :return: None
        """
        pass

    def close(self):
        """
        Method to close the monitor, performing necessary cleanup operations.
        This could include releasing resources, closing files, or any other termination tasks.

        :return: None
        """
        pass
