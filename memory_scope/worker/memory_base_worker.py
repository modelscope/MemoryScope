from typing import List

from memory_scope.constants.common_constants import MESSAGES, USER_NAME
from memory_scope.handler.global_context import GLOBAL_CONTEXT
from memory_scope.models.base_model import BaseModel
from memory_scope.node.message import Message
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

    @property
    def messages(self) -> List[Message]:
        return self.context[MESSAGES]

    @messages.setter
    def messages(self, value):
        self.context[MESSAGES] = value

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            GLOBAL_CONTEXT.model_dict.get(self.embedding_model_name)
        return self._embedding_model

    @property
    def generation_model(self):
        if self._generation_model is None:
            GLOBAL_CONTEXT.model_dict.get(self.generation_model_name)
        return self._generation_model

    @property
    def rank_model(self):
        if self._rank_model is None:
            GLOBAL_CONTEXT.model_dict.get(self.rank_model_name)
        return self._rank_model

    @property
    def user_name(self):
        return self.context[USER_NAME]
