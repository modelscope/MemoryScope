from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from memory_scope.chat.base_memory_chat import BaseMemoryChat
from memory_scope.enumeration.language_enum import LanguageEnum
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.models.base_model import BaseModel
from memory_scope.storage.base_monitor import BaseMonitor
from memory_scope.storage.base_memory_store import BaseMemoryStore


class GlobalContext(object):
    def __init__(self):
        self.global_config: Dict[str, Any] = {}
        self.worker_config: Dict[str, Dict[str, Any]] = {}

        self.memory_service_dict: Dict[str, BaseMemoryService] = {}
        self.model_dict: Dict[str, BaseModel] = {}
        self.memory_chat_dict: Dict[str, BaseMemoryChat] = {}

        self.memory_store: BaseMemoryStore | None = None
        self.monitor: BaseMonitor | None = None
        self.thread_pool: ThreadPoolExecutor | None = None
        self.language: LanguageEnum = LanguageEnum.EN

        self.meta_data: Dict[str, Any] = {}


G_CONTEXT = GlobalContext()
