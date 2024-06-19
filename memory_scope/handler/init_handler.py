import json
import os
import re
from typing import Dict, Any

from memory_scope.db.base_db_client import BaseDBClient
from memory_scope.models.base_model import BaseModel
from memory_scope.monitor.base_monitor import BaseMonitor
from memory_scope.utils.tool_functions import init_instance_by_config_v2
from memory_scope.worker.base_worker import BaseWorker


class InitHandler(object):

    def __init__(self, path: str):
        self.path: str = path
        self.config_name: str = os.path.basename(path)
        self.config_base_dir: str = os.path.dirname(path)

        self.config: dict = {}
        self.global_configs: Dict[str, Any] = {}
        self.worker_dict: Dict[str, BaseWorker] = {}
        self.model_dict: Dict[str, BaseModel] = {}
        self.db_client: BaseDBClient | None = None
        self.monitor: BaseMonitor | None = None

        self.worker_base_dir: str = ""
        self.model_base_dir: str = ""
        self.db_base_dir: str = ""
        self.minitor_base_dir: str = ""

        self.retrieve_pipeline: list = []
        self.summary_short_pipeline: list = []
        self.summary_long_pipeline: list = []

    def init(self):
        with open(self.path) as f:
            self.config = json.load(f)

        self.init_global_config(self.config["global"])

        self.init_workers(self.config["workers"])
        self.init_db(self.config["db"])
        self.init_chat_model(self.config["chat_model"])
        self.init_monitor(self.config["monitor"])

        self.retrieve_pipeline = self.parse_pipeline(self.config["pipelines"]["retrieve"])
        self.summary_short_pipeline = self.parse_pipeline(self.config["pipelines"]["summary_short"])
        self.summary_long_pipeline = self.parse_pipeline(self.config["pipelines"]["summary_long"])

    def init_global_config(self, global_configs: Dict[str, str]):
        """set global_configs & set apikey into env
        """
        self.worker_base_dir = global_configs["worker_base_dir"]
        self.model_base_dir = global_configs["model_base_dir"]
        self.db_base_dir = global_configs["db_base_dir"]
        self.minitor_base_dir = global_configs["minitor_base_dir"]

        # TODO sen

    def init_workers(self, worker_config_name: str):
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
                                                                       **self.global_configs)

            self.init_model(worker_config.get("embedding_model"))
            self.init_model(worker_config.get("generation_model"))
            self.init_model(worker_config.get("rank_model"))

    def init_model(self, model_name: str):
        if not model_name or model_name in self.model_dict:
            return

        with open(os.path.join(self.config_base_dir, "model", model_name)) as f:
            model_config = json.load(f)
            self.model_dict[model_name] = init_instance_by_config_v2(model_config,
                                                                     default_clazz_path=self.model_base_dir)

    def init_db(self, db_config: dict):
        self.db_client = init_instance_by_config_v2(db_config, default_clazz_path=self.db_base_dir)

    def init_chat_model(self, chat_model_config: dict):
        chat_model_name = chat_model_config["name"]
        self.init_model(chat_model_name)

    def init_monitor(self, monitor_config: dict):
        self.monitor = init_instance_by_config_v2(monitor_config, default_clazz_path=self.db_base_dir)

    @staticmethod
    def parse_pipeline(pipeline_str: str) -> list:
        # re-match e.g., [a|b],c,[d,e,f|g,h],j
        pattern = r'(\[[^\]]*\]|[^,]+)'
        pipeline_split = re.findall(pattern, pipeline_str)

        pipeline_list = []
        for pipeline_part in pipeline_split:
            # e.g., [d,e,f|g,h]
            pipeline_part = pipeline_part.strip()
            if '[' in pipeline_part or ']' in pipeline_part:
                pipeline_part = pipeline_part.replace('[', '').replace(']', '')

            # e.g., ["d,e,f", "g,h"]
            line_split = [x.strip() for x in pipeline_part.split("|") if x]
            if len(line_split) <= 0:
                continue

            # e.g., ["d","e","f"]
            pipeline_list.append([x.split(",") for x in line_split])

        return pipeline_list
