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
        self.kwargs = kwargs

        self._operation_dict: Dict[str, BaseOperation] = {}
        self._op_description_dict: Dict[str, str] = {}
        self.logger = Logger.get_logger()

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

    @abstractmethod
    def add_messages(self, messages: List[Message] | Message):
        raise NotImplementedError

    @abstractmethod
    def init_service(self, **kwargs):
        raise NotImplementedError

    def start_backend_service(self):
        pass

    def stop_backend_service(self):
        pass

    def do_operation(self, op_name: str, **kwargs):
        """
        Executes a specific operation by its name with provided keyword arguments.

        Args:
            op_name (str): The name of the operation to execute.
            **kwargs: Keyword arguments for the operation's execution.

        Returns:
            The result of the operation execution, if any. Otherwise, None.

        Raises:
            Warning: If the operation name is not initialized in `_operation_dict`.
        """
        if op_name not in self._operation_dict:
            self.logger.warning(f"op_name={op_name} is not inited!")
            return
        return self._operation_dict[op_name].run_operation(**kwargs)

    def __getattr__(self, name: str):
        return lambda **kwargs: self.do_operation(name, **kwargs)


