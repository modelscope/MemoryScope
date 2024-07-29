from abc import ABCMeta, abstractmethod
from typing import Optional, Literal

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
                         temporary_memories: Optional[str] = None,
                         history_message_strategy: Literal["auto", None] | int = "auto",
                         remember_response: bool = True,
                         **kwargs):
        """
        The core function that carries out conversation with memory accepts user queries through query and returns the
        conversation results through model_response. The retrieved memories are stored in the memories within meta_data.
        Args:
            query (str): User's query, includes the user's question.
            role_name (str, optional): User's role name.
            system_prompt (str, optional): System prompt. Defaults to the system_prompt in "memory_chat_prompt.yaml".
            memory_prompt (str, optional): Memory prompt, It takes effect when there is a memory and will be placed in
                front of the retrieved memory. Defaults to the memory_prompt in "memory_chat_prompt.yaml".
            temporary_memories (str, optional): Manually added user memory in this function.
            history_message_strategy ("auto", None, int):
                - If it is set to "auto"， the history messages in the conversation will retain those that have not
                    yet been summarized. Default to "auto".
                - If it is set to None， no conversation history will be saved.
                - If it is set to an integer value "n", the most recent "n" messages will be retained.
            remember_response (bool, optional): Flag indicating whether to save the AI's response to memory.
                Defaults to False.
        Returns:
            - ModelResponse: In non-streaming mode, returns a complete AI response.
            - ModelResponseGen: In streaming mode, returns a generator yielding AI response parts.
            - Memories: To obtain the memory by invoking the method of model_response.meta_data[MEMORIES]
        """
        raise NotImplementedError

    def start_backend_service(self):
        self.memory_service.start_backend_service()

    def run_service_operation(self, name: str, **kwargs):
        return self.memory_service.run_operation(name, **kwargs)

    def run(self):
        """
        Abstract method to run the chat system.

        This method should contain the logic to initiate and manage the chat process,
        utilizing the memory service as needed. It must be implemented by subclasses.
        """
        pass
