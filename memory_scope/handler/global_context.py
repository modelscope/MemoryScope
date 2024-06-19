from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from memory_scope.chat.base_memory_chat import BaseMemoryChat
from memory_scope.db.base_db_client import BaseDBClient
from memory_scope.models.base_model import BaseModel
from memory_scope.monitor.base_monitor import BaseMonitor
from memory_scope.worker.base_worker import BaseWorker


class GlobalContext(object):
    def __init__(self):
        self.global_configs: Dict[str, Any] = {}

        self.worker_dict: Dict[str, BaseWorker] = {}

        self.model_dict: Dict[str, BaseModel] = {}

        self.memory_chat_dict: Dict[str, BaseMemoryChat] = {}

        self.db_client: BaseDBClient | None = None

        self.monitor: BaseMonitor | None = None

        self.thread_pool: ThreadPoolExecutor | None = None


GLOBAL_CONTEXT = GlobalContext()
