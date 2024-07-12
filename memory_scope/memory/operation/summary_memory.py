from memory_scope.constants.common_constants import RESULT, CHAT_KWARGS
from memory_scope.memory.operation.base_backend_operation import BaseBackendOperation
from memory_scope.memory.operation.base_operation import OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow


class SummaryMemory(BaseWorkflow, BaseBackendOperation):
    """
    A class that combines workflow management and backend operations to process and summarize data.

    This class inherits functionality from both `BaseWorkflow` for managing workflow steps and
    `BaseBackendOperation` for executing backend-specific tasks.
    """
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self, **kwargs):
        """
        Initializes the SummaryMemory instance, setting up both workflow and backend operation capabilities.

        Args:
            **kwargs: Additional keyword arguments used in initializing the parent classes.
        """
        super().__init__(**kwargs)  # Initialize the BaseWorkflow part of the instance
        BaseBackendOperation.__init__(self, **kwargs)  # Initialize the BaseBackendOperation part

    def init_workflow(self, **kwargs):
        """
        Initializes the workflow with backend settings using provided keyword arguments.
        
        Args:
            **kwargs: Additional keyword arguments to initialize the workflow.
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
        self.context[CHAT_KWARGS] = kwargs
        self.run_workflow()
        result = self.context.get(RESULT)
        return result
