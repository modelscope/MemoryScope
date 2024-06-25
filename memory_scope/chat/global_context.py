from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from chat.base_memory_chat import BaseMemoryChat
from enumeration.language_enum import LanguageEnum
from models.base_model import BaseModel
from storage.base_monitor import BaseMonitor
from storage.base_vector_store import BaseVectorStore
from worker.base_worker import BaseWorker


class GlobalContext(object):
    def __init__(self):
        self.global_configs: Dict[str, Any] = {}

        self.worker_dict: Dict[str, Dict[str, BaseWorker]] = {}

        self.model_dict: Dict[str, BaseModel] = {}

        self.memory_chat_dict: Dict[str, BaseMemoryChat] = {}

        self.vector_store: BaseVectorStore | None = None

        self.monitor: BaseMonitor | None = None

        self.thread_pool: ThreadPoolExecutor | None = None

        self.language: LanguageEnum = LanguageEnum.EN


GLOBAL_CONTEXT = GlobalContext()
