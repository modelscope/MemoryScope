from abc import ABCMeta, abstractmethod
from typing import List, Dict

from memoryscope.memory.operation.base_operation import BaseOperation
from memoryscope.memoryscope_context import MemoryscopeContext
from memoryscope.scheme.message import Message
from memoryscope.utils.logger import Logger


class BaseMemoryService(metaclass=ABCMeta):
    """
    An abstract base class for managing memory operations within a multithreaded context.
    It sets up the infrastructure for operation handling, message storage, and synchronization,
    along with logging capabilities and customizable configurations.
    """

    def __init__(self, memory_operations: Dict[str, dict], context: MemoryscopeContext, **kwargs):
        """
        Initializes the BaseMemoryService with operation definitions, keys for memory access,
        and additional keyword arguments for flexibility.

        Args:
            memory_operations (Dict[str, dict]): A dictionary defining available memory operations.
            **kwargs: Additional parameters to customize service behavior.
        """
        self.memory_operations_conf: Dict[str, dict] = memory_operations
        self.context: MemoryscopeContext = context

        self._operation_dict: Dict[str, BaseOperation] = {}
        self._op_description_dict: Dict[str, str] = {}

        self.logger = Logger.get_logger()
        self.kwargs = kwargs

    def update_kwargs(self, **kwargs):
        pass

    @abstractmethod
    def add_messages(self, messages: List[Message] | Message):
        raise NotImplementedError

    @abstractmethod
    def do_operation(self, op_name: str, **kwargs):
        """
        Abstract method defining the interface for executing a specific operation by its name.
        This method must be implemented by subclasses to provide the actual operation logic.

        Args:
            op_name (str): The name identifying the operation to be performed.
            **kwargs: Additional keyword arguments required for the operation execution.

        Raises:
            NotImplementedError: This exception is raised when the method is not overridden in a subclass.
        """
        raise NotImplementedError

    @property
    def op_description_dict(self) -> Dict[str, str]:
        """
        Property to retrieve a dictionary mapping operation keys to their descriptions.
        Lazily initializes the dictionary on first access.

        Returns:
            Dict[str, str]: A dictionary where keys are operation identifiers and values are their descriptions.
        """
        if not self._op_description_dict:
            self._op_description_dict = {k: v.description for k, v in self._operation_dict.items()}
        return self._op_description_dict

    def retrieve_memory(self):
        """
        Executes the operation associated with retrieved memory.
        Asserts that the operation for retrieved memory has been initialized.

        Returns:
            Any: The result of the retrieved memory operation.
        """
        assert self.retrieve_memory_key in self._operation_dict, f"op={self.retrieve_memory_key} is not inited!"
        return self.do_operation(self.retrieve_memory_key)

    def read_message(self):
        """
        Executes the operation associated with reading messages.
        Asserts that the operation for reading messages has been initialized.

        Returns:
            Any: The result of the read message operation.
        """
        assert self.read_message_key in self._operation_dict, f"op={self.read_message_key} is not inited!"
        return self.do_operation(self.read_message_key)

    @abstractmethod
    def init_service(self, **kwargs):
        raise NotImplementedError

    def start_backend_service(self):
        pass

    def stop_backend_service(self):
        pass
