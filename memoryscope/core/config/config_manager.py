import json
import os
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

import yaml

from memoryscope.core.config.arguments import Arguments
from memoryscope.core.utils.logger import Logger


class ConfigManager(object):

    def __init__(self,
                 config_path: Optional[str] = None,
                 arguments: Optional[Arguments] = None,
                 demo_config_name: str = "demo_config_zh.yaml",
                 **kwargs):
        self.config: dict = {}
        self.kwargs = kwargs
        self.logger = Logger.get_logger("memoryscope")

        if not (config_path or kwargs or arguments):
            raise RuntimeError("can not init config manager without kwargs or --config_path!")

        if config_path:
            self.read_config(config_path)
        else:
            self.read_config((Path(__file__).parent / demo_config_name).__str__())

        kwargs = {k: v for k, v in kwargs.items() if k in [x.name for x in fields(Arguments)]}
        kwargs_padding = {x.name: None for x in fields(Arguments) if x.name not in kwargs}
        kwargs.update(kwargs_padding)

        # (high) when there are environment variables, read them and merge into kwargs
        kwargs_from_env = {x.name:os.environ.get(x.name, None) for x in fields(Arguments) if os.environ.get(x.name, None) is not None}
        kwargs.update(kwargs_from_env)

        # generate argument dataclass
        if not arguments:
            arguments = Arguments(**kwargs)
        else:
            # (highest) when arguments is passed into the memoryscope
            arguments = arguments

        self.update_config_by_arguments(arguments)
        self.logger.info("\n" + self.dump_config())

    def read_config(self, config_path: str):
        if config_path.endswith(".yaml"):
            with open(config_path) as f:
                self.config = yaml.load(f, yaml.FullLoader)

        elif config_path.endswith(".json"):
            with open(config_path) as f:
                self.config = json.load(f)

    @staticmethod
    def update_ignore_none(config, new_config_dict):
        update_dict = {k:v for k, v in new_config_dict.items() if v is not None}
        config.update(update_dict)
        return

    @staticmethod
    def update_global_by_arguments(config: dict, arguments: Arguments):
        ConfigManager.update_ignore_none(
            config,
            {
                "language": arguments.language,
                "thread_pool_max_workers": arguments.thread_pool_max_workers,
                "enable_ranker": arguments.enable_ranker,
                "enable_today_contra_repeat": arguments.enable_today_contra_repeat,
                "enable_long_contra_repeat": arguments.enable_long_contra_repeat,
                "output_memory_max_count": arguments.output_memory_max_count,
            }
        )

    @staticmethod
    def update_memory_chat_by_arguments(config: dict, arguments: Arguments):
        if arguments.memory_chat_class is not None:
            memory_chat_class_split = config["class"].split(".")
            stream = arguments.chat_stream
            if stream is None:
                stream = arguments.memory_chat_class in ["cli_memory_chat", ]
            config.update(
                {
                    "class": ".".join(memory_chat_class_split[:-1] + [arguments.memory_chat_class]),
                    "stream": stream,
                }
            )

    @staticmethod
    def update_memory_service_by_arguments(config: dict, arguments: Arguments):
        ConfigManager.update_ignore_none(config, {
            "human_name": arguments.human_name,
            "assistant_name": arguments.assistant_name,
        })
        if arguments.consolidate_memory_interval_time is not None:
            config["memory_operations"]["consolidate_memory"]["interval_time"] = \
                arguments.consolidate_memory_interval_time

        if arguments.reflect_and_reconsolidate_interval_time is not None:
            config["memory_operations"]["reflect_and_reconsolidate"]["interval_time"] = \
                arguments.reflect_and_reconsolidate_interval_time

    @staticmethod
    def update_worker_by_arguments(config: dict, arguments: Arguments):
        if arguments.worker_params is not None:
            for worker_name, kv_dict in arguments.worker_params.items():
                if worker_name not in config:
                    continue
                config[worker_name].update(kv_dict)

    @staticmethod
    def update_model_by_arguments(config: dict, arguments: Arguments):
        ConfigManager.update_ignore_none(config["generation_model"], {
            "module_name": arguments.generation_backend,
            "model_name": arguments.generation_model,
        })
        if isinstance(arguments.generation_params, dict):
            ConfigManager.update_ignore_none(config["generation_model"], {
                **arguments.generation_params,
            })

        ConfigManager.update_ignore_none(config["embedding_model"], {
            "module_name": arguments.embedding_backend,
            "model_name": arguments.embedding_model,
        })
        if isinstance(arguments.embedding_params, dict):
            ConfigManager.update_ignore_none(config["embedding_model"], {
                **arguments.embedding_params,
            })

        ConfigManager.update_ignore_none(config["rank_model"], {
            "module_name": arguments.rank_backend,
            "model_name": arguments.rank_model,
        })
        if isinstance(arguments.rank_params, dict):
            ConfigManager.update_ignore_none(config["rank_model"], {
                **arguments.rank_params,
            })

    @staticmethod
    def update_memory_store_by_arguments(config: dict, arguments: Arguments):
        ConfigManager.update_ignore_none(config, {
            "index_name": arguments.es_index_name,
            "es_url": arguments.es_url,
            "retrieve_mode": arguments.retrieve_mode}
        )

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
