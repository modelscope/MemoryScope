import json
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

import yaml

from memoryscope.core.config.arguments import Arguments
from memoryscope.core.utils.logger import Logger


class ConfigManager(object):

    def __init__(self,
                 config: dict = None,
                 config_path: Optional[str] = None,
                 arguments: Optional[Arguments] = None,
                 demo_config_name: str = "demo_config.yaml",
                 **kwargs):
        self.config: dict = {}
        self.kwargs = kwargs

        if config:
            self.config = config
            self.logger = self._init_logger()
            self.logger.info("init by config mode:")

        elif config_path:
            self.read_config(config_path)
            self.logger = self._init_logger()
            self.logger.info("init by config_path mode:")

        else:
            self.read_demo_config(demo_config_name)
            if arguments:
                self.update_config_by_arguments(arguments)
                self.logger = self._init_logger()
                self.logger.info(f"init by arguments mode: {arguments.__dict__}")

            elif kwargs:
                kwargs = {k: v for k, v in kwargs.items() if k in [x.name for x in fields(Arguments)]}
                arguments = Arguments(**kwargs)
                self.update_config_by_arguments(arguments)
                self.logger = self._init_logger()
                self.logger.info(f"init by kwargs mode: {kwargs}")

            else:
                raise RuntimeError("can not init config manager without kwargs!")
        self.logger.info(self.dump_config())

    def _init_logger(self) -> Logger:
        global_config = self.config["global"]
        logger_name = global_config["logger_name"]
        logger_name_time_suffix = global_config["logger_name_time_suffix"]
        if logger_name_time_suffix:
            suffix = datetime.now().strftime(logger_name_time_suffix)
            logger_name = f"{logger_name}_{suffix}"
        return Logger.get_logger(logger_name, to_stream=global_config["logger_to_screen"])

    def read_config(self, config_path: str):
        if config_path.endswith(".yaml"):
            with open(config_path) as f:
                self.config = yaml.load(f, yaml.FullLoader)

        elif config_path.endswith(".json"):
            with open(config_path) as f:
                self.config = json.load(f)

    def read_demo_config(self, demo_config_name: str):
        file_path = Path(__file__)
        demo_config_path = (file_path.parent / demo_config_name).__str__()
        with open(demo_config_path) as f:
            self.config = yaml.load(f, yaml.FullLoader)

    @staticmethod
    def update_global_by_arguments(config: dict, arguments: Arguments):
        config.update({
            "language": arguments.language,
            "thread_pool_max_workers": arguments.thread_pool_max_workers,
            "logger_name": arguments.logger_name,
            "logger_name_time_suffix": arguments.logger_name_time_suffix,
            "logger_to_screen": arguments.logger_to_screen,
            "use_dummy_ranker": arguments.use_dummy_ranker,
        })

    @staticmethod
    def update_memory_chat_by_arguments(config: dict, arguments: Arguments):
        memory_chat_class_split = config["class"].split(".")
        stream = arguments.memory_chat_class in ["cli_memory_chat", ]
        config.update({
            "class": ".".join(memory_chat_class_split[:-1] + [arguments.memory_chat_class]),
            "human_name": arguments.human_name if arguments.human_name else "",
            "assistant_name": arguments.assistant_name if arguments.assistant_name else "",
            "stream": stream,
        })

    @staticmethod
    def update_memory_service_by_arguments(config: dict, arguments: Arguments):
        config.update({
            "human_name": arguments.human_name if arguments.human_name else "",
            "assistant_name": arguments.assistant_name if arguments.assistant_name else "",
        })
        config["memory_operations"]["consolidate_memory"]["interval_time"] = \
            arguments.consolidate_memory_interval_time
        config["memory_operations"]["reflect_and_reconsolidate"]["interval_time"] = \
            arguments.reflect_and_reconsolidate_interval_time

    @staticmethod
    def update_worker_by_arguments(config: dict, arguments: Arguments):
        for worker_name, kv_dict in arguments.worker_params.items():
            if worker_name not in config:
                continue
            config[worker_name].update(kv_dict)

    @staticmethod
    def update_model_by_arguments(config: dict, arguments: Arguments):
        config["generation_model"].update({
            "module_name": arguments.generation_backend,
            "model_name": arguments.generation_model,
            **arguments.generation_params,
        })

        config["embedding_model"].update({
            "module_name": arguments.embedding_backend,
            "model_name": arguments.embedding_model,
            **arguments.embedding_params,
        })

        config["rank_model"].update({
            "module_name": arguments.rank_backend,
            "model_name": arguments.rank_model,
            **arguments.rank_params,
        })

    @staticmethod
    def update_memory_store_by_arguments(config: dict, arguments: Arguments):
        config.update({
            "index_name": arguments.es_index_name,
            "es_url": arguments.es_url,
            "retrieve_mode": arguments.retrieve_mode})

    def update_config_by_arguments(self, arguments: Arguments):
        # prepare global
        self.update_global_by_arguments(self.config["global"], arguments)

        # prepare memory chat
        memory_chat_conf_dict = self.config["memory_chat"]
        memory_chat_config = list(memory_chat_conf_dict.values())[0]
        self.update_memory_chat_by_arguments(memory_chat_config, arguments)

        # prepare memory service
        memory_service_conf_dict = self.config["memory_service"]
        memory_service_config = list(memory_service_conf_dict.values())[0]
        self.update_memory_service_by_arguments(memory_service_config, arguments)

        # prepare worker
        self.update_worker_by_arguments(self.config["worker"], arguments)

        # prepare model
        self.update_model_by_arguments(self.config["model"], arguments)

        # prepare memory store
        self.update_memory_store_by_arguments(self.config["memory_store"], arguments)

    def add_node_object(self, node: str, name: str, config: dict):
        self.config[node][name] = config

    def pop_node_object(self, node: str, name: str):
        return self.config[node].pop(name, None)

    def clear_node_all(self, node: str):
        self.config[node].clear()

    def dump_config(self, file_type: Literal["json", "yaml"] = "yaml", file_path: Optional[str] = None) -> str:
        if file_type == "json":
            content = json.dumps(self.config, indent=2, ensure_ascii=False)
        elif file_type == "yaml":
            content = yaml.dump(self.config, indent=2, allow_unicode=True)
        else:
            raise NotImplementedError

        if file_path:
            with open(file_path, "w") as f:
                f.write(content)

        return content
