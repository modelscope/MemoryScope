from abc import ABCMeta, abstractmethod
from typing import Optional

from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.logger import Logger


class BaseMemoryChat(metaclass=ABCMeta):
    """
    An abstract base class representing a chat system integrated with memory services.
    It outlines the method to initiate a chat session leveraging memory data, which concrete subclasses must implement.
    """

    def __init__(self, **kwargs):
        self.kwargs: dict = kwargs
        self.logger = Logger.get_logger()

    @property
    def memory_service(self) -> BaseMemoryService:
        """
        Abstract property to access the memory service.

        Raises:
            NotImplementedError: This method should be implemented in a subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def chat_with_memory(self,
                         query: str,
                         role_name: Optional[str] = None,
                         system_prompt: Optional[str] = None,
                         memory_prompt: Optional[str] = None,
                         extra_memories: Optional[str] = None,
                         add_messages: bool = True,
                         remember_response: bool = True,
                         **kwargs):

        raise NotImplementedError

    def run(self):
        """
        Abstract method to run the chat system.

        This method should contain the logic to initiate and manage the chat process,
        utilizing the memory service as needed. It must be implemented by subclasses.
        """
        pass
