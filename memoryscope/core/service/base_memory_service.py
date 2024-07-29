from abc import ABCMeta, abstractmethod
from typing import List, Dict

from memoryscope.core.memoryscope_context import MemoryscopeContext
from memoryscope.core.operation.base_operation import BaseOperation
from memoryscope.core.utils.logger import Logger
from memoryscope.scheme.message import Message


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
        self.kwargs = kwargs

        self._operation_dict: Dict[str, BaseOperation] = {}
        self.chat_messages: List[Message] = []
        self.logger = Logger.get_logger()

    @property
    def op_description_dict(self) -> Dict[str, str]:
        """
        Property to retrieve a dictionary mapping operation keys to their descriptions.
        Returns:
            Dict[str, str]: A dictionary where keys are operation identifiers and values are their descriptions.
        """
        return {k: v.description for k, v in self._operation_dict.items()}

    @abstractmethod
    def add_messages(self, messages: List[Message] | Message):
        raise NotImplementedError

    @abstractmethod
    def register_operation(self, name: str, operation_config: dict, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def init_service(self, **kwargs):
        raise NotImplementedError

    def start_backend_service(self, name: str = None):
        pass

    def stop_backend_service(self, wait_service_end: bool = False):
        pass

    def run_operation(self, name: str, **kwargs):
        """
        Executes a specific operation by its name with provided keyword arguments.

        Args:
            name (str): The name of the operation to execute.
            **kwargs: Keyword arguments for the operation's execution.

        Returns:
            The result of the operation execution, if any. Otherwise, None.

        Raises:
            Warning: If the operation name is not initialized in `_operation_dict`.
        """
        if name not in self._operation_dict:
            self.logger.warning(f"operation={name} is not registered!")
            return
        return self._operation_dict[name].run_operation(**kwargs)

    def __getattr__(self, name: str):
        assert name in self._operation_dict, f"operation={name} is not registered!"
        return lambda **kwargs: self.run_operation(name=name, **kwargs)
