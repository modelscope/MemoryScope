import time
from abc import abstractmethod

from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger


class BaseBackendOperation(BaseOperation):
    """
    BaseBackendOperation serves as an abstract base class for defining backend operations within a specified time interval.
    It manages operation status, loop control, and integrates with a logging facility and a global context for thread management.
    """
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self, interval_time: int, **kwargs):
        """
        Initializes the BaseBackendOperation instance with an interval time for recurring operations.

        Args:
            interval_time (int): The time interval in seconds at which the operation should run.
            **kwargs: Additional keyword arguments passed to the parent class's initializer.
        """
        super(BaseBackendOperation, self).__init__(**kwargs)

        self.interval_time: int = interval_time

        self._operation_status_run: bool = False
        self._loop_switch: bool = False
        self._run_thread = None

        self.logger = Logger.get_logger()

    @abstractmethod
    def _run_operation(self, **kwargs):
        """
        Abstract method to define the logic of the operation executed by the backend.

        This method needs to be implemented by any subclass of BaseBackendOperation.
        It serves as the core execution unit for backend-specific tasks.

        Args:
            **kwargs: Arbitrary keyword arguments that might be necessary for the operation.

        Raises:
            NotImplementedError: If the method is not overridden in a subclass.
        """
        raise NotImplementedError

    def run_operation(self, **kwargs):
        """
        Executes the operation defined by `_run_operation` method with given keyword arguments,
        while managing the operation status and exception handling.

        Args:
            **kwargs: Arbitrary keyword arguments to be passed to `_run_operation`.

        Returns:
            The result of the `_run_operation` method if no exception occurs, otherwise None.
        """
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
        """
        Loops until _loop_switch is False, sleeping for 1 second in each interval.
        At each interval, it checks if _loop_switch is still True, and if so, executes the operation.
        """
        while self._loop_switch:
            for _ in range(self.interval_time):
                if self._loop_switch:
                    time.sleep(1)
                else:
                    break
            if self._loop_switch:
                self.run_operation()

    def run_operation_backend(self):
        """
        Initiates the background operation loop if it's not already running.
        Sets the _loop_switch to True and submits the _loop_operation to a thread from the global thread pool.
        """
        if not self._loop_switch:
            self._loop_switch = True
            self._run_thread = G_CONTEXT.thread_pool.submit(self._loop_operation)

    def stop_operation_backend(self):
        """
        Stops the background operation loop by setting the _loop_switch to False.
        """
        self._loop_switch = False
