from abc import ABCMeta, abstractmethod
from typing import Literal

OPERATION_TYPE = Literal["frontend", "backend"]


class BaseOperation(metaclass=ABCMeta):
    """
    An abstract base class representing an operation that can be categorized as either frontend or backend.
    
    Attributes:
        operation_type (OPERATION_TYPE): Specifies the type of operation, defaulting to "frontend".
        name (str): The name of the operation.
        description (str): A description of the operation.
    """

    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self, name: str, description: str = ""):
        """
        Initializes a new instance of the BaseOperation.

        Args:
            name (str): The name identifying the operation.
            description (str): An optional description detailing the operation's purpose or behavior.
        """
        self.name: str = name
        self.description: str = description

    def init_workflow(self, **kwargs):
        """
        Initialize the workflow with additional keyword arguments if needed.

        Args:
            **kwargs: Additional parameters for initializing the workflow.
        """
        pass

    @abstractmethod
    def run_operation(self, **kwargs):
        """
        Abstract method to define the operation to be run. 
        Subclasses must implement this method.

        Args:
            **kwargs: Keyword arguments for running the operation.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError

    def start_operation_backend(self):
        """
        Placeholder method for running an operation specific to the backend.
        Intended to be overridden by subclasses if backend operations are required.
        """
        pass

    def stop_operation_backend(self, wait_task_end: bool = False):
        """
        Placeholder method to stop any ongoing backend operations.
        Should be implemented in subclasses where backend operations are managed.
        """
        pass
