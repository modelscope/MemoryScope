from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from memoryscope.core.chat.base_memory_chat import BaseMemoryChat
from memoryscope.core.config.config_manager import ConfigManager
from memoryscope.core.memoryscope_context import MemoryscopeContext
from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.enumeration.language_enum import LanguageEnum
from memoryscope.enumeration.model_enum import ModelEnum


class MemoryScope(ConfigManager):

    def __init__(self, **kwargs):
        self._context: MemoryscopeContext = MemoryscopeContext()
        self._context.memory_scope_uuid = datetime.now().strftime(r"%Y%m%d_%H%M%S")
        super().__init__(**kwargs)
        self._init_context_by_config()

    def _init_context_by_config(self):
        # set global config
        global_conf = self.config["global"]
        self._context.language = LanguageEnum(global_conf["language"])
        self._context.thread_pool = ThreadPoolExecutor(max_workers=global_conf["thread_pool_max_workers"])
        self._context.meta_data.update({
            "enable_ranker": global_conf["enable_ranker"],
            "enable_today_contra_repeat": global_conf["enable_today_contra_repeat"],
            "enable_long_contra_repeat": global_conf["enable_long_contra_repeat"],
            "output_memory_max_count": global_conf["output_memory_max_count"],
        })

        if not global_conf["enable_ranker"]:
            self.logger.warning("If a semantic ranking model is not available, MemoryScope will use cosine similarity "
                                "scoring as a substitute. However, the ranking effectiveness will be somewhat "
                                "compromised.")

        # init memory_chat
        memory_chat_conf_dict = self.config["memory_chat"]
        if memory_chat_conf_dict:
            for name, conf in memory_chat_conf_dict.items():
                self._context.memory_chat_dict[name] = init_instance_by_config(conf, name=name, context=self._context)

        # set memory_service
        memory_service_conf_dict = self.config["memory_service"]
        assert memory_service_conf_dict
        for name, conf in memory_service_conf_dict.items():
            self._context.memory_service_dict[name] = init_instance_by_config(conf, name=name, context=self._context)

        # init model
        model_conf_dict = self.config["model"]
        assert model_conf_dict
        for name, conf in model_conf_dict.items():
            self._context.model_dict[name] = init_instance_by_config(conf, name=name)

        # init memory_store
        memory_store_conf = self.config["memory_store"]
        assert memory_store_conf
        emb_model_name: str = memory_store_conf[ModelEnum.EMBEDDING_MODEL.value]
        embedding_model = self._context.model_dict[emb_model_name]
        self._context.memory_store = init_instance_by_config(memory_store_conf, embedding_model=embedding_model)

        # init monitor
        monitor_conf = self.config["monitor"]
        if monitor_conf:
            self._context.monitor = init_instance_by_config(monitor_conf)

        # set worker config
        self._context.worker_conf_dict = self.config["worker"]

    def close(self):
        # wait service to stop
        for _, service in self._context.memory_service_dict.items():
            service.stop_backend_service(wait_service=True)

        self._context.thread_pool.shutdown()

        self._context.memory_store.close()

        if self._context.monitor:
            self._context.monitor.close()

        self.logger.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.warning(f"An exception occurred: {exc_type.__name__}: {exc_val}\n{exc_tb}")
        self.close()

    @property
    def content(self):
        return self._context

    @property
    def memory_chat_dict(self):
        return self._context.memory_chat_dict

    @property
    def memory_service_dict(self):
        return self._context.memory_service_dict

    @property
    def default_memory_chat(self) -> BaseMemoryChat:
        return list(self.memory_chat_dict.values())[0]

    @property
    def default_memory_service(self) -> BaseMemoryService:
        return list(self.memory_service_dict.values())[0]

    @classmethod
    def cli_memory_chat(cls, **kwargs):
        with cls(**kwargs) as ms:
            memory_chat = ms.default_memory_chat
            memory_chat.run()
