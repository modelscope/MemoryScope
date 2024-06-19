import json
import os.path
from typing import Dict

from memory_scope.models.base_model import BaseModel
from memory_scope.utils.tool_functions import init_instance_by_config_v2
from memory_scope.worker.base_worker import BaseWorker


class ConfigHandler(object):

    def __init__(self, path: str):
        self.config_name: str = os.path.basename(path)
        self.config_base_dir: str = os.path.dirname(path)

        with open(path) as f:
            config = json.load(f)

        self.global_configs: Dict[str, str] = {}
        self.worker_dict: Dict[str, BaseWorker] = {}
        self.model_dict: Dict[str, BaseModel] = {}

        self._init_global_config(config["global"])
        self.worker_base_dir = self.global_configs.get("worker_base_dir", "config")
        self.model_base_dir = self.global_configs.get("model_base_dir", "config/model")
        self._init_workers(config["workers"])
        self._init_db(config["db"])
        self._init_chat_model(config["chat_model"])
        self._init_monitor(config["monitor"])

    def _init_global_config(self, global_configs: Dict[str, str]):
        """set global_configs & set apikey into env
        """

    def _init_workers(self, worker_config_name: str):
        """ load worker config & init workers
        """
        with open(os.path.join(self.config_base_dir, worker_config_name)) as f:
            worker_config_dict = json.load(f)

        for worker_name, worker_config in worker_config_dict.items():
            if worker_name in self.worker_dict:
                continue
            self.worker_dict[worker_name] = init_instance_by_config_v2(worker_config,
                                                                       default_clazz_path=self.worker_base_dir,
                                                                       suffix_name="worker",
                                                                       **self.global_configs,
                                                                       **worker_config)

            self._init_model(worker_config.get("embedding_model"))
            self._init_model(worker_config.get("generation_model"))
            self._init_model(worker_config.get("rank_model"))

    def _init_model(self, model_name: str):
        if not model_name or model_name in self.model_dict:
            return

        with open(os.path.join(self.model_base_dir, model_name)) as f:
            model_config = json.load(f)
            self.model_dict[model_name] = init_instance_by_config_v2(model_config,
                                                                     default_clazz_path=self.model_base_dir,
                                                                     suffix_name="",
                                                                     **model_config)

    def _init_db(self, db_config: dict):
        pass

    def _init_chat_model(self, chat_model_config: dict):
        chat_model_name = chat_model_config["name"]
        self._init_model(chat_model_name)

    def _init_monitor(self, monitor_config: dict):
        pass
