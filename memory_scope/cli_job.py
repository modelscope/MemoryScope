import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

import yaml

from chat_v2.global_context import G_CONTEXT
from enumeration.language_enum import LanguageEnum
from enumeration.model_enum import ModelEnum
from utils.logger import Logger
from utils.tool_functions import (
    complete_config_name,
    init_instance_by_config,
)


class CliJob(object):

    def __init__(self, config_path: str, config_suffix: str = ".yaml"):
        self.config_path: str = config_path
        self.config_suffix: str = config_suffix

        self.config: Dict[str, Any] = {}
        self.global_config: Dict[str, Any] = {}

        self.logger: Logger = Logger.get_logger("memory_chat")

    def init_model(self, model_name: str):
        if not model_name or model_name in G_CONTEXT.model_dict:
            return

        with open(os.path.join(self.config_base_dir, "model", complete_config_name(model_name))) as f:
            model_config = json.load(f)
        GLOBAL_CONTEXT.model_dict[model_name] = init_instance_by_config(model_config)

    def init_workers(self):
        """load worker config & init workers"""
        worker_config_name: str = self.config["workers"]
        with open(
                os.path.join(self.config_base_dir, complete_config_name(worker_config_name))
        ) as f:
            worker_config_dict = json.load(f)

        for worker_name, worker_config in worker_config_dict.items():
            if worker_name not in self.worker_chat_dict:
                continue

            chat_name_list = self.worker_chat_dict[worker_name]
            for chat_name in chat_name_list:
                if chat_name not in GLOBAL_CONTEXT.worker_dict:
                    GLOBAL_CONTEXT.worker_dict[chat_name] = {}
                GLOBAL_CONTEXT.worker_dict[chat_name][worker_name] = (
                    init_instance_by_config(
                        worker_config,
                        suffix_name="worker",
                        **GLOBAL_CONTEXT.global_configs,
                    )
                )

            self.init_model(worker_config.get(ModelEnum.EMBEDDING_MODEL.value))
            self.init_model(worker_config.get(ModelEnum.GENERATION_MODEL.value))
            self.init_model(worker_config.get(ModelEnum.RANK_MODEL.value))

    @staticmethod
    def set_global_config():
        # TODO at sen, set global_configs & set apikey into env
        G_CONTEXT.language = LanguageEnum(G_CONTEXT.global_configs["language"])
        G_CONTEXT.thread_pool = ThreadPoolExecutor(max_workers=int(G_CONTEXT.global_configs["max_workers"]))

    def init_global_content_by_config(self):
        config_path = self.config_path
        if not self.config_path.endswith(self.config_suffix):
            config_path += self.config_suffix

        with open(config_path) as f:
            self.config = yaml.load(f, yaml.FullLoader)

        G_CONTEXT.global_configs = self.global_config = self.config["global_configs"]
        self.set_global_config()

        # init memory_chat
        for chat_name in self.global_config["chat_list"]:
            memory_chat_config = self.config[chat_name]
            G_CONTEXT.memory_chat_dict[chat_name] = init_instance_by_config(memory_chat_config, chat_name=chat_name)

        for model_config in

        GLOBAL_CONTEXT.model_dict[model_name] = init_instance_by_config(model_config)

        # TODO no db and monitor now
        GLOBAL_CONTEXT.vector_store = init_instance_by_config(
            self.config["vector_store"]
        )
        GLOBAL_CONTEXT.monitor = init_instance_by_config(self.config["monitor"])

    @staticmethod
    def run():
        with GLOBAL_CONTEXT.thread_pool:
            memory_chat = list(GLOBAL_CONTEXT.memory_chat_dict.values())[0]
            memory_chat.run()
