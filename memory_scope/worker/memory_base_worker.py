from typing import List, Dict

from ..chat.global_context import GLOBAL_CONTEXT
from ..constants.common_constants import MESSAGES, CHAT_NAME
from ..models.base_model import BaseModel
from ..scheme.message import Message
from ..storage.base_monitor import BaseMonitor
from ..storage.base_vector_store import BaseVectorStore
from ..worker.base_worker import BaseWorker
from ..scheme.memory_node import MemoryNode
from ..constants import common_constants


class MemoryBaseWorker(BaseWorker):
    def __init__(
        self, embedding_model: str, generation_model: str, rank_model: str, **kwargs
    ):
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
    def chat_name(self):
        return self.get_context(CHAT_NAME)

    @property
    def embedding_model(self) -> BaseModel:
        if self._embedding_model is None:
            self._embedding_model = GLOBAL_CONTEXT.model_dict.get(
                self.embedding_model_name
            )
        return self._embedding_model

    @property
    def generation_model(self) -> BaseModel:
        if self._generation_model is None:
            self._generation_model = GLOBAL_CONTEXT.model_dict.get(
                self.generation_model_name
            )
        return self._generation_model

    @property
    def rank_model(self) -> BaseModel:
        if self._rank_model is None:
            self._rank_model = GLOBAL_CONTEXT.model_dict.get(self.rank_model_name)
        return self._rank_model

    @property
    def vector_store(self) -> BaseVectorStore:
        if self._vector_store is None:
            self._vector_store = GLOBAL_CONTEXT.vector_store
        return self._vector_store

    @property
    def monitor(self):
        if self._monitor is None:
            self._monitor = GLOBAL_CONTEXT.monitor
        return self._monitor

    @property
    def user_profile_dict(self) -> Dict[str, MemoryNode]:
        if not self._user_profile_dict:
            self._user_profile_dict = {
                user_attr.meta_data.get("memory_key", ""): user_attr
                for user_attr in self.get_context(common_constants.USER_PROFILE)
            }
        return self._user_profile_dict

    @property
    def memory_id(self) -> str:
        pass

    def __getattr__(self, key):
        return self.kwargs[key]

    def get_prompt(self, x):
        return x[GLOBAL_CONTEXT.global_configs["language"]]