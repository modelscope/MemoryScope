from abc import ABCMeta
from typing import List, Dict, Set, Any

from memory_scope.constants.common_constants import CHAT_MESSAGES, CHAT_KWARGS, CONTEXT_MEMORY_DICT
from memory_scope.memory.worker.base_worker import BaseWorker
from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.utils.global_context import G_CONTEXT
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
            rank_model (str): Identifier or instance of the ranking model for sorting or prioritizing data.
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
        return self.get_context(CHAT_MESSAGES)

    @chat_messages.setter
    def chat_messages(self, value):
        self.set_context(CHAT_MESSAGES, value)


    @property
    def chat_kwargs(self) -> Dict[str, str]:
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
            self._embedding_model = G_CONTEXT.model_dict[self._embedding_model]  # ⭐ Retrieve the actual model instance when the attribute is a string reference
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
            self._generation_model = G_CONTEXT.model_dict[self._generation_model]  # ⭐ Retrieve the model instance if currently a string reference
        return self._generation_model

    @property
    def rank_model(self) -> BaseModel:
        """
        Property to access the rank model. If the stored rank model is a string, it fetches the actual model instance 
        from the global context's model dictionary before returning it.

        Returns:
            BaseModel: The rank model instance used for ranking tasks within the conversation management system.
        """
        if isinstance(self._rank_model, str):
            self._rank_model = G_CONTEXT.model_dict[self._rank_model]  # Fetch model instance if string reference
        return self._rank_model

    @property
    def memory_store(self) -> BaseMemoryStore:
        """
        Property to access the memory store. If not initialized, it fetches the memory store from the global context.

        Returns:
            BaseMemoryStore: The memory store instance associated with this worker.
        """
        if self._memory_store is None:
            self._memory_store = G_CONTEXT.memory_store
        return self._memory_store

    @property
    def contex_memory_dict(self) -> Dict[str, MemoryNode]:
        """
        Retrieves the context memory dictionary. If it does not exist, initializes it first.

        Returns:
            Dict[str, MemoryNode]: The dictionary storing context memory nodes.
        """
        if not self.has_content(CONTEXT_MEMORY_DICT):
            self.set_context(CONTEXT_MEMORY_DICT, {})  # Initialize context memory dict if not present
        return self.get_context(CONTEXT_MEMORY_DICT)

    def get_memories(self, keys: str | List[str]) -> List[MemoryNode]:
        """
        Retrieves memory nodes associated with the given keys.

        This method accepts a single key or a list of keys. For each key, it fetches the 
        associated memory IDs from the context. If memory IDs are found, they are used to 
        collect the corresponding MemoryNode objects from the contex_memory_dict. The final 
        result is a list of unique MemoryNode values, avoiding duplicates.

        Args:
            keys (str | List[str]): The key or list of keys to retrieve memories for.

        Returns:
            List[MemoryNode]: A list of MemoryNode objects associated with the input keys.
        """
        memories: Dict[str, MemoryNode] = {}
        if isinstance(keys, str):
            keys = [keys]

        for key in keys:
            memory_ids: List[str] = self.get_context(key)
            if memory_ids:
                memories.update({x: self.contex_memory_dict[x] for x in memory_ids})
        return list(memories.values())

    def set_memories(self, key: str, nodes: MemoryNode | List[MemoryNode], log_repeat: bool = True):
        """
        Stores or updates multiple memory nodes in the context, optionally logging if a memory ID is repeated.

        Args:
            key (str): The key under which to categorize the memory nodes in the context.
            nodes (MemoryNode | List[MemoryNode]): A single MemoryNode instance or a list of MemoryNode instances to be set.
            log_repeat (bool, optional): If True, logs a warning when a memory ID is encountered more than once. Defaults to True.

        Notes:
            - If 'nodes' is None, it is treated as an empty list.
            - If 'nodes' is a single MemoryNode instance, it is converted into a list containing that single node.
            - Existing memory nodes with duplicate IDs are skipped, with an optional warning logged.
        """
        if nodes is None:
            nodes = []
        elif isinstance(nodes, MemoryNode):
            nodes = [nodes]
        for node in nodes:
            if node.memory_id in self.contex_memory_dict:
                if log_repeat:
                    self.logger.warning(f"repeated_id memory id={node.memory_id} content={node.content} "
                                        f"status={node.status}")
                continue
            self.contex_memory_dict[node.memory_id] = node
            self.logger.info(f"add to memory context memory id={node.memory_id} content={node.content} "
                             f"status={node.status}")
        self.set_context(key, [n.memory_id for n in nodes])

    def save_memories(self, keys: str | List[str] = None):
        """
        Saves memories from the context to the memory store. If no keys are provided,
        all memories are saved and the context is cleared. If keys are provided, only
        the associated memories are saved and removed from the context.

        Args:
            keys (str | List[str], optional): The keys identifying which memories to save.
                If None, all memories are saved. Defaults to None.
        """
        if keys is None:
            self.memory_store.update_memories(list(self.contex_memory_dict.values()))  # Save all memories and clear context
            self.contex_memory_dict.clear()
            return

        if isinstance(keys, str):
            keys = [keys]

        ids: Set[str] = set()  # corrected type annotation for Python typing
        for key in keys:
            t_ids: List[str] = self.get_context(key)
            if t_ids:
                ids.update(t_ids)
        nodes = [self.contex_memory_dict.pop(_) for _ in ids]  # Remove and collect nodes by IDs
        self.memory_store.update_memories(nodes)  # Save collected nodes to memory store

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
        Property to get the user name from the meta_data of the global context.
        If not set initially, it retrieves the 'assistant_name' as the user name.

        Returns:
            str: The name of the user.
        """
        if self._user_name is None:
            self._user_name = G_CONTEXT.meta_data["assistant_name"]
        return self._user_name

    @property
    def target_name(self) -> str:
        """
        Retrieves the target name, initializing it from meta_data if not set.

        Returns:
            str: The human-readable name of the target.
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

    def __getattr__(self, key: str):
        """
        Custom attribute access to directly retrieve values from kwargs.

        Args:
            key (str): The attribute key to look up in kwargs.

        Returns:
            Any: The value associated with the key in kwargs.
        """
        return self.kwargs[key]

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
