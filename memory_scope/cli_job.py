from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

import yaml

from chat_v2.global_context import G_CONTEXT
from enumeration.language_enum import LanguageEnum
from utils.logger import Logger
from utils.tool_functions import init_instance_by_config


class CliJob(object):

    def __init__(self, config_path: str, config_suffix: str = ".yaml"):
        self.config_path: str = config_path
        self.config_suffix: str = config_suffix
        self.config: Dict[str, Any] = {}

        self.logger: Logger = Logger.get_logger("cli_job")

    @staticmethod
    def set_global_config(global_config: Dict[str, Any]):
        """ set global_configs & set apikey into env
        :return:
        TODO at sen
        """
        G_CONTEXT.global_config = global_config
        G_CONTEXT.language = LanguageEnum(global_config["language"])
        G_CONTEXT.thread_pool = ThreadPoolExecutor(max_workers=int(global_config["max_workers"]))

    def init_global_content_by_config(self):
        # load config
        config_path = self.config_path
        if not self.config_path.endswith(self.config_suffix):
            config_path += self.config_suffix
        with open(config_path) as f:
            self.config = yaml.load(f, yaml.FullLoader)

        # set global_config
        self.set_global_config(self.config["global_config"])

        # init memory_chat
        for name, conf in self.config["memory_chat"].items():
            G_CONTEXT.memory_chat_dict[name] = init_instance_by_config(conf, name=name)

        # set memory_service
        for name, conf in self.config["memory_service"].items():
            G_CONTEXT.memory_service_dict[name] = init_instance_by_config(conf, name=name)

        # init models
        for name, conf in self.config["models"].items():
            G_CONTEXT.model_dict[name] = init_instance_by_config(conf, name=name)

        # init vector_store
        G_CONTEXT.vector_store = init_instance_by_config(self.config["vector_store"])

        # init monitor
        G_CONTEXT.monitor = init_instance_by_config(self.config["monitor"])

        # set worker config
        G_CONTEXT.worker_config = self.config["workers"]

    @staticmethod
    def run():
        with G_CONTEXT.thread_pool:
            memory_chat = list(G_CONTEXT.memory_chat_dict.values())[0]
            memory_chat.run()
