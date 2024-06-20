from typing import List

from memory_scope.chat.global_context import GLOBAL_CONTEXT
from memory_scope.constants.common_constants import MESSAGES, USER_NAME
from memory_scope.definition.message import Message
from memory_scope.models.base_model import BaseModel
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.storage.base_vector_store import BaseVectorStore
from memory_scope.worker.base_worker import BaseWorker


class MemoryBaseWorker(BaseWorker):
    def __init__(self,
                 embedding_model: str,
                 generation_model: str,
                 rank_model: str,
                 **kwargs):
        super(MemoryBaseWorker, self).__init__(**kwargs)
        self.embedding_model_name: str = embedding_model
        self.generation_model_name: str = generation_model
        self.rank_model_name: str = rank_model

        self._embedding_model: BaseModel | None = None
        self._generation_model: BaseModel | None = None
        self._rank_model: BaseModel | None = None

        self._vector_store: BaseVectorStore | None = None
        self._monitor: BaseMonitor | None = None

    @property
    def messages(self) -> List[Message]:
        return self.get_context(MESSAGES)

    @messages.setter
    def messages(self, value):
        self.set_context(MESSAGES, value)

    @property
    def user_name(self):
        return self.get_context(USER_NAME)

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            self._embedding_model = GLOBAL_CONTEXT.model_dict.get(self.embedding_model_name)
        return self._embedding_model

    @property
    def generation_model(self):
        if self._generation_model is None:
            self._generation_model = GLOBAL_CONTEXT.model_dict.get(self.generation_model_name)
        return self._generation_model

    @property
    def rank_model(self):
        if self._rank_model is None:
            self._rank_model = GLOBAL_CONTEXT.model_dict.get(self.rank_model_name)
        return self._rank_model

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = GLOBAL_CONTEXT.vector_store
        return self._vector_store

    @property
    def monitor(self):
        if self._monitor is None:
            self._monitor = GLOBAL_CONTEXT.monitor
        return self._monitor
