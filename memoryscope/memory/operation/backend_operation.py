import time
from typing import List

from memoryscope.constants.common_constants import CHAT_KWARGS, RESULT, CHAT_MESSAGES
from memoryscope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memoryscope.memory.operation.base_workflow import BaseWorkflow
from memoryscope.scheme.message import Message
from memoryscope.utils.global_context import G_CONTEXT
from memoryscope.utils.logger import Logger


class BackendOperation(BaseWorkflow, BaseOperation):
    """
    BaseBackendOperation serves as an abstract base class for defining backend operations.
    It manages operation status, loop control, and integrates with a global context for thread management.
    """
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self,
                 name: str,
                 description: str,
                 chat_messages: List[Message],
                 interval_time: int,
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)

        self.chat_messages: List[Message] = chat_messages
        self.interval_time: int = interval_time

        self._operation_status_run: bool = False
        self._loop_switch: bool = False
        self._run_thread = None

        self.logger = Logger.get_logger()

    def init_workflow(self, **kwargs):
        """
        Initializes the workflow by setting up workers with provided keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments to be passed during worker initialization.
        """
        self.init_workers(is_backend=True, **kwargs)

    def _run_operation(self, **kwargs):
        """
        Executes an operation within the workflow by clearing the context,
        setting chat arguments, running the workflow, and returning the result.

        Args:
            **kwargs: Keyword arguments necessary for the operation, including chat parameters.

        Returns:
            Any: The result obtained after executing the workflow.
        """
        self.context.clear()

        # Add additional arguments to the context
        kwargs.update(**self.kwargs)
        self.context[CHAT_KWARGS] = kwargs

        # Include the most recent messages in the operation context
        self.context[CHAT_MESSAGES] = self.chat_messages

        # Execute the workflow with the prepared context
        self.run_workflow()

        # Retrieve the result from the context after workflow execution
        return self.context.get(RESULT)

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