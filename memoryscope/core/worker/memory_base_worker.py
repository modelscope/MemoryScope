from abc import ABCMeta
from typing import List, Dict, Any

from memoryscope.constants.common_constants import (CHAT_MESSAGES, CHAT_KWARGS, WORKFLOW_NAME, MEMORY_MANAGER,
                                                    USER_NAME, TARGET_NAME, CHAT_MESSAGES_SCATTER)
from memoryscope.constants.language_constants import DEFAULT_HUMAN_NAME, USER_NAME_EXPRESSION
from memoryscope.core.models.base_model import BaseModel
from memoryscope.core.storage.base_memory_store import BaseMemoryStore
from memoryscope.core.storage.base_monitor import BaseMonitor
from memoryscope.core.utils.prompt_handler import PromptHandler
from memoryscope.core.worker.base_worker import BaseWorker
from memoryscope.core.worker.memory_manager import MemoryManager
from memoryscope.enumeration.language_enum import LanguageEnum
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.scheme.message import Message


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
        self._prompt_handler: PromptHandler | None = None

    @property
    def chat_messages(self) -> List[List[Message]]:
        """
        Property to get the chat messages.

        Returns:
            List[Message]: List of chat messages.
        """
        return self.get_workflow_context(CHAT_MESSAGES)

    @property
    def chat_messages_scatter(self) -> List[Message]:
        """
        Property to get the chat messages.

        Returns:
            List[Message]: List of chat messages.
        """
        result = self.get_workflow_context(CHAT_MESSAGES_SCATTER)

        if not result:
            if not self.chat_messages:
                return []

            if isinstance(self.chat_messages[0], list):
                chat_messages: List[Message] = []
                for messages in self.chat_messages:
                    if messages:
                        chat_messages.extend(messages)
                chat_messages.sort(key=lambda _: _.time_created)
                self.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)

            else:
                assert isinstance(self.chat_messages[0], Message)
                self.set_workflow_context(CHAT_MESSAGES_SCATTER, self.chat_messages)

        return self.get_workflow_context(CHAT_MESSAGES_SCATTER)

    @chat_messages_scatter.setter
    def chat_messages_scatter(self, value: List[Message]):
        """
        Set the chat messages with the new value.
        """

        self.set_workflow_context(CHAT_MESSAGES_SCATTER, value)

    @property
    def chat_kwargs(self) -> Dict[str, Any]:
        """
        Retrieves the chat keyword arguments from the context.

        This property getter fetches the chat-related parameters stored in the context,
        which are used to configure how chat interactions are handled.

        Returns:
            Dict[str, str]: A dictionary containing the chat keyword arguments.
        """
        return self.get_workflow_context(CHAT_KWARGS)

    @property
    def user_name(self) -> str:
        return self.get_workflow_context(USER_NAME)

    @property
    def target_name(self) -> str:
        return self.get_workflow_context(TARGET_NAME)

    @property
    def workflow_name(self) -> str:
        return self.get_workflow_context(WORKFLOW_NAME)

    @property
    def language(self) -> LanguageEnum:
        return self.memoryscope_context.language

    @property
    def embedding_model(self) -> BaseModel:
        """
        Property to get the embedding model. If the model is currently stored as a string,
        it will be replaced with the actual model instance from the global context's model dictionary.

        Returns:
            BaseModel: The embedding model used for converting text into vector representations.
        """
        if isinstance(self._embedding_model, str):
            self._embedding_model = self.memoryscope_context.model_dict[self._embedding_model]
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
            self._generation_model = self.memoryscope_context.model_dict[self._generation_model]
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
            self._rank_model = self.memoryscope_context.model_dict[self._rank_model]
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
            self._memory_store = self.memoryscope_context.memory_store
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
            self._monitor = self.memoryscope_context.monitor
        return self._monitor

    @property
    def prompt_handler(self) -> PromptHandler:
        """
        Lazily initializes and returns the PromptHandler instance.

        Returns:
            PromptHandler: An instance of PromptHandler initialized with specific file path and keyword arguments.
        """
        if self._prompt_handler is None:
            self._prompt_handler = PromptHandler(self.FILE_PATH, language=self.language, **self.kwargs)
        return self._prompt_handler

    @property
    def memory_manager(self) -> MemoryManager:
        """
        Lazily initializes and returns the MemoryHandler instance.

        Returns:
            MemoryHandler: An instance of MemoryHandler.
        """
        if not self.has_content(MEMORY_MANAGER):
            self.set_workflow_context(MEMORY_MANAGER, MemoryManager(self.memoryscope_context, workerflow_name=self.workflow_name))
        return self.get_workflow_context(MEMORY_MANAGER)

    def get_language_value(self, languages: dict | List[dict]) -> Any | List[Any]:
        """
        Retrieves the value(s) corresponding to the current language context.

        Args:
            languages (dict | list[dict]): A dictionary or list of dictionaries containing language-keyed values.

        Returns:
            Any | list[Any]: The value or list of values matching the current language setting.
        """
        if isinstance(languages, list):
            return [x[self.language] for x in languages]
        return languages[self.language]

    def prompt_to_msg(self,
                      system_prompt: str,
                      few_shot: str,
                      user_query: str,
                      concat_system_prompt: bool = True) -> List[Message]:
        """
        Converts input strings into a structured list of message objects suitable for AI interactions.

        Args:
            system_prompt (str): The system-level instruction or context.
            few_shot (str): An example or demonstration input, often used for illustrating expected behavior.
            user_query (str): The actual user query or prompt to be processed.
            concat_system_prompt(bool): Concat system prompt again or not in the user message.
                A simple method to improve the effectiveness for some LLMs. Defaults to True.

        Returns:
            List[Message]: A list of Message objects, each representing a part of the conversation setup.
        """
        system_content = ""
        if self.target_name != DEFAULT_HUMAN_NAME[self.language]:
            system_content += USER_NAME_EXPRESSION[self.language].format(name=self.target_name)
        system_content += system_prompt.strip()
        system_message = Message(role=MessageRoleEnum.SYSTEM.value, content=system_content)

        if concat_system_prompt:
            user_content_list = [system_content, '\n', few_shot, '\n', user_query]
        else:
            user_content_list = [few_shot, '\n', user_query]
        user_message = Message(role=MessageRoleEnum.USER.value,
                               content="\n".join([x.strip() for x in user_content_list]))
        return [system_message, user_message]
