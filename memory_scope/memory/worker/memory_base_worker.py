from abc import ABCMeta
from typing import List, Dict, Set

from memory_scope.constants.common_constants import CHAT_MESSAGES, CHAT_KWARGS
from memory_scope.memory.worker.base_worker import BaseWorker
from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.prompt_handler import PromptHandler


class MemoryBaseWorker(BaseWorker, metaclass=ABCMeta):

    def __init__(self,
                 embedding_model: str = "",
                 generation_model: str = "",
                 rank_model: str = "",
                 **kwargs):
        super(MemoryBaseWorker, self).__init__(**kwargs)

        self._embedding_model: BaseModel | str = embedding_model
        self._generation_model: BaseModel | str = generation_model
        self._rank_model: BaseModel | str = rank_model

        self._memory_store: BaseMemoryStore | None = None
        self._monitor: BaseMonitor | None = None

        self._user_name: str | None = None
        self._target_name: str | None = None
        self._prompt_handler: PromptHandler | None = None

        self._contex_memory_dict: Dict[str, MemoryNode] = {}

    @property
    def chat_messages(self) -> List[Message]:
        return self.get_context(CHAT_MESSAGES)

    @chat_messages.setter
    def chat_messages(self, value):
        self.set_context(CHAT_MESSAGES, value)

    @property
    def chat_kwargs(self) -> Dict[str, str]:
        return self.get_context(CHAT_KWARGS)

    @property
    def embedding_model(self) -> BaseModel:
        if isinstance(self._embedding_model, str):
            self._embedding_model = G_CONTEXT.model_dict[self._embedding_model]
        return self._embedding_model

    @property
    def generation_model(self) -> BaseModel:
        if isinstance(self._generation_model, str):
            self._generation_model = G_CONTEXT.model_dict[self._generation_model]
        return self._generation_model

    @property
    def rank_model(self) -> BaseModel:
        if isinstance(self._rank_model, str):
            self._rank_model = G_CONTEXT.model_dict[self._rank_model]
        return self._rank_model

    @property
    def memory_store(self) -> BaseMemoryStore:
        if self._memory_store is None:
            self._memory_store = G_CONTEXT.memory_store
        return self._memory_store

    def get_memories(self, keys: str | List[str]) -> List[MemoryNode]:
        memories: List[MemoryNode] = []
        if isinstance(keys, str):
            keys = [keys]

        for key in keys:
            memory_ids: List[str] = self.get_context(key)
            if memory_ids:
                memories.extend([self._contex_memory_dict[x] for x in memory_ids])
        return memories

    def set_memories(self, key: str, nodes: MemoryNode | List[MemoryNode]):
        if nodes is None:
            nodes = []
        elif isinstance(nodes, MemoryNode):
            nodes = [nodes]

        for node in nodes:
            if node.memory_id in self._contex_memory_dict:
                continue
            self._contex_memory_dict[node.memory_id] = node
        self.set_context(key, [n.memory_id for n in nodes])

    def save_memories(self, keys: str | List[str] = None):
        if keys is None:
            self.memory_store.update_memories(list(self._contex_memory_dict.values()))
            self._contex_memory_dict.clear()
            return

        if isinstance(keys, str):
            keys = [keys]

        ids: Set[str] = Set[str]()
        for key in keys:
            t_ids: List[str] = self.get_context(key)
            if t_ids:
                ids.update(t_ids)
        nodes = [self._contex_memory_dict.pop(_) for _ in ids]
        self.memory_store.update_memories(nodes)

    @property
    def monitor(self) -> BaseMonitor:
        if self._monitor is None:
            self._monitor = G_CONTEXT.monitor
        return self._monitor

    @property
    def user_name(self) -> str:
        if self._user_name is None:
            self._user_name = G_CONTEXT.meta_data["human_name"]
        return self._user_name

    @property
    def target_name(self) -> str:
        if self._target_name is None:
            self._target_name = G_CONTEXT.meta_data["assistant_name"]
        return self._target_name

    @property
    def prompt_handler(self) -> PromptHandler:
        if self._prompt_handler is None:
            self._prompt_handler = PromptHandler(__file__, **self.kwargs)
        return self._prompt_handler

    def __getattr__(self, key: str):
        return self.kwargs[key]

    @staticmethod
    def get_language_value(languages: dict | list[dict]) -> str | list[str]:
        if isinstance(languages, list):
            return [x[G_CONTEXT.language] for x in languages]
        return languages[G_CONTEXT.language]
