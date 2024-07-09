import sys

sys.path.append(".")  # noqa: E402

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

import fire
import yaml

from memory_scope.enumeration.language_enum import LanguageEnum
from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger
from memory_scope.utils.timer import timer
from memory_scope.utils.tool_functions import init_instance_by_config


class CliJob(object):

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.logger: Logger = Logger.get_logger("cli_job", to_stream=False)

    def load_config(self, path: str):
        with open(path) as f:
            if path.endswith("yaml"):
                self.config = yaml.load(f, yaml.FullLoader)
            elif path.endswith("json"):
                self.config = json.load(f)
            else:
                raise RuntimeError("not supported config file type!")
        self.init_global_content_by_config()

    def set_global_config(self):
        G_CONTEXT.global_config = global_config = self.config["global_config"]
        G_CONTEXT.language = LanguageEnum(global_config["language"])
        G_CONTEXT.thread_pool = ThreadPoolExecutor(max_workers=int(global_config["max_workers"]))

    @timer
    def init_global_content_by_config(self):
        # set global config
        self.set_global_config()

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
        memory_store_config = self.config["memory_store"]
        embedding_model = G_CONTEXT.model_dict[memory_store_config[ModelEnum.EMBEDDING_MODEL.value]]
        G_CONTEXT.memory_store = init_instance_by_config(memory_store_config, embedding_model=embedding_model)

        # init monitor
        G_CONTEXT.monitor = init_instance_by_config(self.config["monitor"])

        # set worker config
        G_CONTEXT.worker_config = self.config["worker"]

    def run(self, config: str):
        self.load_config(config)

        # with G_CONTEXT.thread_pool:
        memory_chat = list(G_CONTEXT.memory_chat_dict.values())[0]
        memory_chat.run()

        G_CONTEXT.memory_store.close()
        G_CONTEXT.monitor.close()
        G_CONTEXT.thread_pool.shutdown()


if __name__ == "__main__":
    cli_job = CliJob()
    fire.Fire(cli_job.run)
