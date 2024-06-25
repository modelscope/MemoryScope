from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

import pydantic

from memory_scope.chat_v2.base_memory_chat import BaseMemoryChat
from memory_scope.enumeration.language_enum import LanguageEnum
from memory_scope.models.base_model import BaseModel
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.storage.base_vector_store import BaseVectorStore


class GlobalContext(pydantic.BaseModel):
    global_config: Dict[str, Any] = pydantic.Field({}, description="global configs")
    model_dict: Dict[str, BaseModel] = pydantic.Field({}, description="global model_dict")
    memory_chat_dict: Dict[str, BaseMemoryChat] = pydantic.Field({}, description="global memory_chat_dict")
    vector_store: BaseVectorStore | None = pydantic.Field(None, description="global vector_store")
    monitor: BaseMonitor | None = pydantic.Field(None, description="global monitor")
    thread_pool: ThreadPoolExecutor | None = pydantic.Field(None, description="global thread_pool")
    language: LanguageEnum = pydantic.Field(LanguageEnum.CN, description="language: cn / en")


G_CONTEXT = GlobalContext()
