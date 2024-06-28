from abc import ABCMeta
from typing import List

from memory_scope.chat.global_context import G_CONTEXT
from memory_scope.memory.worker.base_worker import BaseWorker
from memory_scope.models.base_model import BaseModel
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.storage.base_vector_store import BaseVectorStore


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

        self._vector_store: BaseVectorStore | None = None
        self._monitor: BaseMonitor | None = None

    @property
    def messages(self) -> List[Message]:
        return self.get_context(MESSAGES)

    @messages.setter
    def messages(self, value):
        self.set_context(MESSAGES, value)

    @property
    def chat_name(self):
        return self.get_context(CHAT_NAME)

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
    def vector_store(self) -> BaseVectorStore:
        if self._vector_store is None:
            self._vector_store = G_CONTEXT.vector_store
        return self._vector_store

    @property
    def monitor(self):
        if self._monitor is None:
            self._monitor = G_CONTEXT.monitor
        return self._monitor

    @property
    def memory_id(self) -> str:
        pass

    def __getattr__(self, key: str):
        return self.kwargs[key]

    def get_prompt(self, x):
        return x[GLOBAL_CONTEXT.global_configs["language"]]