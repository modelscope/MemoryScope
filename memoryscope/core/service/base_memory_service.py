from abc import ABCMeta, abstractmethod
from typing import List, Dict

from memoryscope.constants.language_constants import DEFAULT_HUMAN_NAME
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

    def __init__(self,
                 memory_operations: Dict[str, dict],
                 context: MemoryscopeContext,
                 assistant_name: str = None,
                 human_name: str = None,
                 **kwargs):
        """
        Initializes the BaseMemoryService with operation definitions, keys for memory access,
        and additional keyword arguments for flexibility.

        Args:
            memory_operations (Dict[str, dict]): A dictionary defining available memory operations.
            context (MemoryscopeContext): runtime context.
            human_name (str): human name.
            assistant_name (str): assistant name.
            **kwargs: Additional parameters to customize service behavior.
        """
        self._operations_conf: Dict[str, dict] = memory_operations
        self._context: MemoryscopeContext = context
        self._human_name: str = human_name
        self._assistant_name: str = assistant_name
        self._kwargs = kwargs

        if not self._human_name:
            self._human_name = DEFAULT_HUMAN_NAME[self._context.language]
        if not self._assistant_name:
            self._assistant_name = "AI"

        self._operation_dict: Dict[str, BaseOperation] = {}
        self._chat_messages: List[List[Message]] = []
        self._role_names: List[str] = []

        self.logger = Logger.get_logger()

    @property
    def human_name(self) -> str:
        return self._human_name

    @property
    def assistant_name(self) -> str:
        return self._assistant_name

    def get_chat_messages_scatter(self, recent_n_pair: int) -> List[Message]:
        chat_messages_scatter: List[Message] = []
        for messages in self._chat_messages[-recent_n_pair:]:
            chat_messages_scatter.extend(messages)
        return chat_messages_scatter

    @property
    def op_description_dict(self) -> Dict[str, str]:
        """
        Property to retrieve a dictionary mapping operation keys to their descriptions.
        Returns:
            Dict[str, str]: A dictionary where keys are operation identifiers and values are their descriptions.
        """
        return {k: v.description for k, v in self._operation_dict.items()}

    @abstractmethod
    def add_messages_pair(self, messages: List[Message]):
        raise NotImplementedError

    @abstractmethod
    def register_operation(self, name: str, operation_config: dict, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def init_service(self, **kwargs):
        raise NotImplementedError

    def start_backend_service(self, name: str = None, **kwargs):
        pass

    def stop_backend_service(self, wait_service: bool = False):
        pass

    @abstractmethod
    def run_operation(self, name: str, role_name: str = "", **kwargs):
        raise NotImplementedError

    def __getattr__(self, name: str):
        assert name in self._operation_dict, f"operation={name} is not registered!"
        return lambda **kwargs: self.run_operation(name=name, **kwargs)
