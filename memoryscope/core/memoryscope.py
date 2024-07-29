from concurrent.futures import ThreadPoolExecutor

from memoryscope.core.chat.base_memory_chat import BaseMemoryChat
from memoryscope.core.config.config_manager import ConfigManager
from memoryscope.core.memoryscope_context import MemoryscopeContext
from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.enumeration.language_enum import LanguageEnum
from memoryscope.enumeration.model_enum import ModelEnum


class MemoryScope(ConfigManager):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.context: MemoryscopeContext = MemoryscopeContext()
        self.init_context_by_config()

    def init_context_by_config(self):
        # set global config
        global_conf = self.config["global"]
        self.context.language = LanguageEnum(global_conf["language"])
        self.context.thread_pool = ThreadPoolExecutor(max_workers=global_conf["thread_pool_max_workers"])
        self.context.meta_data["use_dummy_ranker"] = global_conf["use_dummy_ranker"]

        # init memory_chat
        memory_chat_conf_dict = self.config["memory_chat"]
        if memory_chat_conf_dict:
            for name, conf in memory_chat_conf_dict.items():
                self.context.memory_chat_dict[name] = init_instance_by_config(conf, name=name, context=self.context)

        # set memory_service
        memory_service_conf_dict = self.config["memory_service"]
        assert memory_service_conf_dict
        for name, conf in memory_service_conf_dict.items():
            self.context.memory_service_dict[name] = init_instance_by_config(conf, name=name, context=self.context)

        # init model
        model_conf_dict = self.config["model"]
        assert model_conf_dict
        for name, conf in model_conf_dict.items():
            self.context.model_dict[name] = init_instance_by_config(conf, name=name)

        # init memory_store
        memory_store_conf = self.config["memory_store"]
        assert memory_store_conf
        emb_model_name: str = memory_store_conf[ModelEnum.EMBEDDING_MODEL.value]
        embedding_model = self.context.model_dict[emb_model_name]
        self.context.memory_store = init_instance_by_config(memory_store_conf, embedding_model=embedding_model)

        # init monitor
        monitor_conf = self.config["monitor"]
        if monitor_conf:
            self.context.monitor = init_instance_by_config(monitor_conf)

        # set worker config
        self.context.worker_conf_dict = self.config["worker"]

    def close(self):
        # wait service to stop
        for _, service in self.context.memory_service_dict.items():
            service.stop_backend_service(wait_service_end=True)

        self.context.thread_pool.shutdown()

        self.context.memory_store.close()

        if self.context.monitor:
            self.context.monitor.close()

        self.logger.close()

    def __enter__(self):
        self.init_context_by_config()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def memory_chat_dict(self):
        return self.context.memory_chat_dict

    @property
    def memory_service_dict(self):
        return self.context.memory_service_dict

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
