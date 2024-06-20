import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

import fire

from handler.global_context import GLOBAL_CONTEXT
from memory_scope.enumeration.model_type import ModelType
from memory_scope.utils.logger import Logger
from memory_scope.utils.timer import Timer
from memory_scope.utils.tool_functions import complete_config_name, init_instance_by_config_v2


class CliJob(object):

    def __init__(self, config_path: str):
        self.config_path: str = config_path
        self.config_base_dir: str = os.path.dirname(config_path)

        self.config: Dict[str, Any] = {}

        self.logger: Logger = Logger.get_logger("memory_chat")

    def init_memory_chat(self):
        for chat in self.config["chat_list"]:
            memory_chat_config = self.config[chat]
            memory_chat = init_instance_by_config_v2(memory_chat_config)
            GLOBAL_CONTEXT.memory_chat_dict[chat] = memory_chat

            generation_model = memory_chat_config[ModelType.GENERATION_MODEL.value]
            self.init_model(generation_model)

    def init_model(self, model_name: str):
        if not model_name or model_name in GLOBAL_CONTEXT.model_dict:
            return

        with open(os.path.join(self.config_base_dir, "model", complete_config_name(model_name))) as f:
            model_config = json.load(f)
        GLOBAL_CONTEXT.model_dict[model_name] = init_instance_by_config_v2(model_config)

    def init_workers(self):
        """ load worker config & init workers
        """
        worker_config_name: str = self.config["workers"]
        with open(os.path.join(self.config_base_dir, complete_config_name(worker_config_name))) as f:
            worker_config_dict = json.load(f)

        for worker_name, worker_config in worker_config_dict.items():
            if worker_name in GLOBAL_CONTEXT.worker_dict:
                raise RuntimeError(f"worker_name={worker_name} is repeated!")

            GLOBAL_CONTEXT.worker_dict[worker_name] = init_instance_by_config_v2(worker_config,
                                                                                 suffix_name="worker",
                                                                                 **GLOBAL_CONTEXT.global_configs)

            self.init_model(worker_config.get(ModelType.EMBEDDING_MODEL.value))
            self.init_model(worker_config.get(ModelType.GENERATION_MODEL.value))
            self.init_model(worker_config.get(ModelType.RANK_MODEL.value))

    def set_global_config(self):
        """set global_configs & set apikey into env
        """

    def init_global_content_by_config(self):
        with open(complete_config_name(self.config_path)) as f:
            self.config = json.load(f)

        GLOBAL_CONTEXT.global_configs = self.config["global_configs"]
        self.set_global_config()
        GLOBAL_CONTEXT.thread_pool = ThreadPoolExecutor(max_workers=int(GLOBAL_CONTEXT.global_configs["max_workers"]))

        self.init_workers()
        GLOBAL_CONTEXT.db_client = init_instance_by_config_v2(self.config["db"])
        GLOBAL_CONTEXT.monitor = init_instance_by_config_v2(self.config["monitor"])

        self.init_memory_chat()

    def run(self):
        with GLOBAL_CONTEXT.thread_pool, Timer("job", log_time=False) as t:
            memory_chat = list(GLOBAL_CONTEXT.memory_chat_dict.values())[0]
            while True:
                query = input("wait for input:")
                if query in ["stop", "停止"]:
                    break
                memory_chat.chat_with_memory(query=query)

            self.logger.info(f"chat complete. cost={t.cost_str}")


def main(config_path: str):
    job = CliJob(config_path=config_path)
    job.init_global_content_by_config()
    job.run()


if __name__ == "__main__":
    fire.Fire(main)
