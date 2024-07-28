from abc import ABCMeta, abstractmethod

from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.logger import Logger


class BaseMemoryChat(metaclass=ABCMeta):
    """
    An abstract base class representing a chat system integrated with memory services.
    It outlines the method to initiate a chat session leveraging memory data, which concrete subclasses must implement.
    """

    def __init__(self, stream: bool = True, **kwargs):
        self.stream: bool = stream
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
                         role_name: str = "",
                         remember_response: bool = True):
        """
        Initiates a chat interaction using the memory service, with the provided query as input.

        Args:
            query (str): The user's query or message to start the chat.
            role_name (str): The role's name.
            remember_response (bool): whether update memory service.
        """
        raise NotImplementedError

    def run(self):
        """
        Abstract method to run the chat system.

        This method should contain the logic to initiate and manage the chat process,
        utilizing the memory service as needed. It must be implemented by subclasses.
        """
        pass
