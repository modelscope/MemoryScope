from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from memory_scope.chat_v2.base_memory_chat import BaseMemoryChat
from memory_scope.enumeration.language_enum import LanguageEnum
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.models.base_model import BaseModel
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.storage.base_vector_store import BaseVectorStore


class GlobalContext(object):
    def __init__(self):
        self.global_config: Dict[str, Any] = {}
        self.worker_config: Dict[str, Any] = {}

        self.memory_service_dict: Dict[str, BaseMemoryService] = {}
        self.model_dict: Dict[str, BaseModel] = {}
        self.memory_chat_dict: Dict[str, BaseMemoryChat] = {}

        self.vector_store: BaseVectorStore | None = None
        self.monitor: BaseMonitor | None = None
        self.thread_pool: ThreadPoolExecutor | None = None
        self.language: LanguageEnum = LanguageEnum.EN


G_CONTEXT = GlobalContext()
