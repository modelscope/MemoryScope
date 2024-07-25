import datetime
import json
from concurrent.futures import ThreadPoolExecutor

import yaml

from memoryscope.argument import default_arguments
from memoryscope.argument.memoryscope_arguments import MemoryscopeArguments
from memoryscope.chat.base_memory_chat import BaseMemoryChat
from memoryscope.enumeration.language_enum import LanguageEnum
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.memory.service.base_memory_service import BaseMemoryService
from memoryscope.memoryscope_context import MemoryscopeContext
from memoryscope.utils.logger import Logger
from memoryscope.utils.tool_functions import init_instance_by_config


class MemoryScope(object):

    def __init__(self,
                 arguments: MemoryscopeArguments | None = None,
                 config: dict | None = None,
                 config_path: str = ""):

        self.global_conf: dict = {}
        self.memory_chat_conf_dict: dict = {}
        self.memory_service_conf_dict: dict = {}
        self.worker_conf_dict: dict = {}
        self.model_conf_dict: dict = {}
        self.memory_store_conf: dict = {}
        self.monitor_conf: dict = {}

        self.context: MemoryscopeContext = MemoryscopeContext()

        if arguments:
            self._init_by_arguments(arguments=arguments)
        elif config:
            self._init_by_config(config=config)
        elif config_path:
            self._init_by_config_path(config_path=config_path)
        else:
            raise RuntimeError("At least one of arguments, config, or file_path must not be empty！")

        self.logger = self._init_logger()

        self._init_context_by_config()

    def _init_by_arguments(self, arguments: MemoryscopeArguments):
        # prepare global
        self.global_conf = {
            "language": arguments.language,
            "thread_pool_max_workers": arguments.thread_pool_max_workers,
            "logger_name": arguments.logger_name,
            "logger_name_time_suffix": arguments.logger_name_time_suffix,
        }

        # prepare memory chat
        self.memory_chat_conf_dict = default_arguments.DEFAULT_MEMORY_CHAT_ARGUMENTS.copy()
        memory_chat_config = list(self.memory_chat_conf_dict.values())[0]
        memory_chat_config.update({
            "class": arguments.memory_chat_class,
            "human_name": arguments.human_name,
            "assistant_name": arguments.assistant_name,
        })

        # prepare memory service
        self.memory_service_conf_dict = default_arguments.DEFAULT_MEMORY_SERVICE_ARGUMENTS.copy()
        memory_service_config = list(self.memory_service_conf_dict.values())[0]
        memory_service_config.update({
            "human_name": arguments.human_name,
            "assistant_name": arguments.assistant_name,
        })
        memory_service_config["memory_operations"]["consolidate_memory"]["interval_time"] = \
            arguments.consolidate_memory_interval_time
        memory_service_config["memory_operations"]["reflect_and_reconsolidate"]["interval_time"] = \
            arguments.reflect_and_reconsolidate_interval_time

        # prepare memory service
        self.worker_conf_dict = default_arguments.DEFAULT_WORKER_ARGUMENTS.copy()
        if arguments.worker_params:
            for worker_name, kv_dict in arguments.worker_params.items():
                if worker_name not in self.worker_conf_dict:
                    continue
                self.worker_conf_dict[worker_name].update(kv_dict)

        # prepare models
        self.model_conf_dict = {
            "generation_model": {
                "class": "models.llama_index_generation_model",
                "module_name": arguments.generation_backend,
                "model_name": arguments.generation_model,
                **arguments.generation_params,
            },
            "embedding_model": {
                "class": "models.llama_index_embedding_model",
                "module_name": arguments.embedding_backend,
                "model_name": arguments.embedding_model,
                **arguments.embedding_params,
            },
            "rank_model": {
                "class": "models.llama_index_rank_model",
                "module_name": arguments.rank_backend,
                "model_name": arguments.rank_model,
                **arguments.rank_params,
            },
        }

        # prepare memory store
        self.memory_store_conf = {
            "class": "storage.llama_index_es_memory_store",
            "embedding_model": "embedding_model",
            "index_name": arguments.es_index_name,
            "es_url": arguments.es_url,
            "retrieve_type": arguments.retrieve_type,
            "hybrid_alpha": arguments.hybrid_alpha,
        }

        self.monitor_conf = default_arguments.DEFAULT_MONITOR_ARGUMENTS.copy()

    def _init_by_config(self, config: dict):
        self.global_conf = config["global_config"]
        self.memory_service_conf_dict = config["memory_service"]
        self.worker_conf_dict = config["worker"]
        self.model_conf_dict = config["model"]
        self.memory_store_conf = config["memory_store"]

        # not necessary
        self.memory_chat_conf_dict = config.get("memory_chat")
        self.monitor_conf = config.get("monitor")

    def _init_by_config_path(self, config_path: str):
        with open(config_path) as f:
            if config_path.endswith("yaml"):
                config = yaml.load(f, yaml.FullLoader)
            elif config_path.endswith("json"):
                config = json.load(f)
            else:
                raise RuntimeError("not supported config file type!")
        return self._init_by_config(config)

    def _init_logger(self) -> Logger:
        logger_name = self.global_conf.get("logger_name")
        assert logger_name, "logger_name is empty!"
        logger_name_time_suffix = self.global_conf.get("logger_name_time_suffix")
        if logger_name_time_suffix:
            suffix = datetime.datetime.now().strftime(logger_name_time_suffix)
            logger_name = f"{logger_name}_{suffix}"
        return Logger.get_logger(logger_name, to_stream=False)

    def _init_context_by_config(self):
        # set global config
        self.context.language = LanguageEnum(self.global_conf["language"])
        self.context.thread_pool = ThreadPoolExecutor(max_workers=self.global_conf["max_workers"])

        # init memory_chat
        if self.memory_chat_conf_dict:
            for name, conf in self.memory_chat_conf_dict.items():
                self.context.memory_chat_dict[name] = init_instance_by_config(conf, name=name, context=self.context)

        # set memory_service
        assert self.memory_service_conf_dict
        for name, conf in self.memory_service_conf_dict.items():
            self.context.memory_service_dict[name] = init_instance_by_config(conf, name=name, context=self.context)

        # init models
        assert self.model_conf_dict
        for name, conf in self.model_conf_dict.items():
            self.context.model_dict[name] = init_instance_by_config(conf, name=name)

        # init vector_store
        assert self.memory_store_conf
        emb_model_name: str = self.memory_store_conf[ModelEnum.EMBEDDING_MODEL.value]
        embedding_model = self.context.model_dict[emb_model_name]
        self.context.memory_store = init_instance_by_config(self.memory_store_conf, embedding_model=embedding_model)

        # init monitor
        if self.monitor_conf:
            self.context.monitor = init_instance_by_config(self.monitor_conf)

        # set worker config
        self.context.worker_config = self.worker_conf_dict

    def close(self):
        for _, service in self.context.memory_service_dict.items():
            service.stop_backend_service()
        self.context.memory_store.close()
        self.context.thread_pool.shutdown()

        if self.context.monitor:
            self.context.monitor.close()

    @property
    def default_memory_chat(self) -> BaseMemoryChat:
        return list(self.context.memory_chat_dict.values())[0]

    @property
    def default_service(self) -> BaseMemoryService:
        return list(self.context.memory_service_dict.values())[0]
