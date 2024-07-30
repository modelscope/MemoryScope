import time

from memoryscope.core.operation.base_operation import OPERATION_TYPE
from memoryscope.core.operation.frontend_operation import FrontendOperation


class BackendOperation(FrontendOperation):
    """
    BaseBackendOperation serves as an abstract base class for defining backend operations.
    It manages operation status, loop control, and integrates with a global context for thread management.
    """
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self, interval_time: int, **kwargs):
        super().__init__(**kwargs)

        self._interval_time: int = interval_time

        self._operation_status_run: bool = False
        self._loop_switch: bool = False
        self._backend_task = None

    def init_workflow(self, **kwargs):
        """
        Initializes the workflow by setting up workers with provided keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments to be passed during worker initialization.
        """
        self.init_workers(is_backend=True, **kwargs)

    def _loop_operation(self, **kwargs):
        """
        Loops until _loop_switch is False, sleeping for 1 second in each interval.
        At each interval, it checks if _loop_switch is still True, and if so, executes the operation.
        """
        while self._loop_switch:
            for _ in range(self._interval_time):
                if self._loop_switch:
                    time.sleep(1)
                else:
                    break

            if self._loop_switch:
                if self._operation_status_run:
                    continue

                self._operation_status_run = True

                if len(self.target_names) > 1:
                    self.logger.warning("current version is not stable under target_names.size > 1!")

                for target_name in self.target_names:
                    try:
                        self.run_operation(target_name=target_name, **kwargs)
                    except Exception as e:
                        self.logger.exception(f"op_name={self.name} target_name={target_name} encounter exception. "
                                              f"args={e.args}")

                self._operation_status_run = False

    def start_operation_backend(self, **kwargs):
        """
        Initiates the background operation loop if it's not already running.
        Sets the _loop_switch to True and submits the _loop_operation to a thread from the global thread pool.
        """
        if not self._loop_switch:
            self._loop_switch = True
            self._backend_task = self.thread_pool.submit(self._loop_operation, **kwargs)
            self.logger.info(f"start operation={self.name}...")

    def stop_operation_backend(self, wait_operation: bool = False):
        """
        Stops the background operation loop by setting the _loop_switch to False.
        """
        self._loop_switch = False
        if self._backend_task:
            if wait_operation:
                self._backend_task.result()
                self.logger.info(f"stop operation={self.name}...")
            else:
                self.logger.info(f"send stop signal to operation={self.name}...")
