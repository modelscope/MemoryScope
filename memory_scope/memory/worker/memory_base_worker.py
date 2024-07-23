from abc import ABCMeta
from typing import List, Dict, Any

from memory_scope.constants.common_constants import CHAT_MESSAGES, CHAT_KWARGS, MEMORY_HANDLER
from memory_scope.memory.worker.base_worker import BaseWorker
from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.message import Message
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.memory_handler import MemoryHandler
from memory_scope.utils.prompt_handler import PromptHandler


class MemoryBaseWorker(BaseWorker, metaclass=ABCMeta):
    FILE_PATH: str = __file__

    def __init__(self,
                 embedding_model: str = "",
                 generation_model: str = "",
                 rank_model: str = "",
                 **kwargs):
        """
        Initializes the MemoryBaseWorker with specified models and configurations.

        Args:
            embedding_model (str): Identifier or instance of the embedding model used for transforming text.
            generation_model (str): Identifier or instance of the text generation model.
            rank_model (str): Identifier or instance of the ranking model for sorting the retrieved memories
                wrt. the semantic similarities.
            **kwargs: Additional keyword arguments passed to the parent class initializer.

        The constructor also initializes key attributes related to memory store, monitoring, 
        user and target identification, and a prompt handler, setting them up for later use.
        """
        super(MemoryBaseWorker, self).__init__(**kwargs)

        self._embedding_model: BaseModel | str = embedding_model
        self._generation_model: BaseModel | str = generation_model
        self._rank_model: BaseModel | str = rank_model

        self._memory_store: BaseMemoryStore | None = None
        self._monitor: BaseMonitor | None = None

        self._user_name: str | None = None
        self._target_name: str | None = None
        self._prompt_handler: PromptHandler | None = None

    @property
    def chat_messages(self) -> List[Message]:
        """
        Property to get the chat messages.

        Returns:
            List[Message]: List of chat messages.
        """
        return self.get_context(CHAT_MESSAGES)

    @chat_messages.setter
    def chat_messages(self, value):
        """
        Set the chat messages with the new value.
        """

        self.set_context(CHAT_MESSAGES, value)

    @property
    def chat_kwargs(self) -> Dict[str, Any]:
        """
        Retrieves the chat keyword arguments from the context.

        This property getter fetches the chat-related parameters stored in the context,
        which are used to configure how chat interactions are handled.

        Returns:
            Dict[str, str]: A dictionary containing the chat keyword arguments.
        """
        return self.get_context(CHAT_KWARGS)

    @property
    def embedding_model(self) -> BaseModel:
        """
        Property to get the embedding model. If the model is currently stored as a string,
        it will be replaced with the actual model instance from the global context's model dictionary.

        Returns:
            BaseModel: The embedding model used for converting text into vector representations.
        """
        if isinstance(self._embedding_model, str):
            self._embedding_model = G_CONTEXT.model_dict[self._embedding_model]
            # ⭐ Retrieve the actual model instance when the attribute is a string reference
        return self._embedding_model

    @property
    def generation_model(self) -> BaseModel:
        """
        Property to access the generation model. If the model is stored as a string,
        it retrieves the actual model instance from the global context's model dictionary.

        Returns:
            BaseModel: The model used for text generation.
        """
        if isinstance(self._generation_model, str):
            self._generation_model = G_CONTEXT.model_dict[self._generation_model]
            # ⭐ Retrieve the model instance if currently a string reference
        return self._generation_model

    @property
    def rank_model(self) -> BaseModel:
        """
        Property to access the rank model. If the stored rank model is a string, it fetches the actual model instance 
        from the global context's model dictionary before returning it.

        Returns:
            BaseModel: The rank model instance used for ranking tasks.
        """
        if isinstance(self._rank_model, str):
            self._rank_model = G_CONTEXT.model_dict[self._rank_model]  # Fetch model instance if string reference
        return self._rank_model

    @property
    def memory_store(self) -> BaseMemoryStore:
        """
        Property to access the memory vector store. If not initialized, it fetches
        the global memory store.

        Returns:
            BaseMemoryStore: The memory store instance used for inserting, updating, retrieving and deleting operations.
        """
        if self._memory_store is None:
            self._memory_store = G_CONTEXT.memory_store
        return self._memory_store

    @property
    def monitor(self) -> BaseMonitor:
        """
        Property to access the monitoring component. If not initialized, it fetches
        the global monitor.

        Returns:
            BaseMonitor: The monitoring component instance.
        """
        if self._monitor is None:
            self._monitor = G_CONTEXT.monitor
        return self._monitor

    @property
    def user_name(self) -> str:
        """
        Property to get the username from the meta_data of the global context.
        If not set initially, it retrieves the 'assistant_name' as the username.

        Returns:
            str: The name of the assistant.
        """
        if self._user_name is None:
            self._user_name = G_CONTEXT.meta_data["assistant_name"]
        return self._user_name

    @property
    def target_name(self) -> str:
        """
        Retrieves the target name, initializing it from meta_data if not set.

        Returns:
            str: The readable name of the human.
        """
        if self._target_name is None:
            self._target_name = G_CONTEXT.meta_data["human_name"]
        return self._target_name

    @property
    def prompt_handler(self) -> PromptHandler:
        """
        Lazily initializes and returns the PromptHandler instance.

        Returns:
            PromptHandler: An instance of PromptHandler initialized with specific file path and keyword arguments.
        """
        if self._prompt_handler is None:
            self._prompt_handler = PromptHandler(self.FILE_PATH, **self.kwargs)
        return self._prompt_handler

    @property
    def memory_handler(self) -> MemoryHandler:
        """
        Lazily initializes and returns the MemoryHandler instance.

        Returns:
            MemoryHandler: An instance of MemoryHandler.
        """
        if not self.has_content(MEMORY_HANDLER):
            self.set_context(MEMORY_HANDLER, MemoryHandler())  # Initialize the memory handler if not present
        return self.get_context(MEMORY_HANDLER)

    @staticmethod
    def get_language_value(languages: dict | list[dict]) -> Any | list[Any]:
        """
        Retrieves the value(s) corresponding to the current language context.

        Args:
            languages (dict | list[dict]): A dictionary or list of dictionaries containing language-keyed values.

        Returns:
            Any | list[Any]: The value or list of values matching the current language setting.
        """
        if isinstance(languages, list):
            return [x[G_CONTEXT.language] for x in languages]
        return languages[G_CONTEXT.language]
