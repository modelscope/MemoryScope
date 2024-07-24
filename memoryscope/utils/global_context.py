from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from memoryscope.chat.base_memory_chat import BaseMemoryChat
from memoryscope.enumeration.language_enum import LanguageEnum
from memoryscope.memory.service.base_memory_service import BaseMemoryService
from memoryscope.models.base_model import BaseModel
from memoryscope.storage.base_memory_store import BaseMemoryStore
from memoryscope.storage.base_monitor import BaseMonitor


class GlobalContext(object):
    """
    The GlobalContext class archives all configs utilized by store, monitor, services and workers.
    """

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
