import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from itertools import zip_longest
from typing import Dict, Any

from worker.memory.base_worker import BaseWorker

from common.context_handler import ContextHandler
from common.logger import Logger
from common.timer import timer, Timer
from common.tool_functions import under_line_to_hump
from constants import common_constants
from constants.common_constants import RESPONSE_EXT_INFO, MAX_WORKERS, PIPELINE
from enumeration.memory_method_enum import MemoryMethodEnum
from request.memory import MemoryServiceRequestModel
from config.env_config import C, Workers
from utils.tool_functions import init_instance_by_config


class MemoryService(object):
    def __init__(self, method: MemoryMethodEnum):
        self.method = method
        self.context_handler = ContextHandler()

        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=C.THREAD_POOL_MAX_COUNT)

        # 全部初始化的worker
        self.worker_dict: Dict[str, BaseWorker] = {}

        # 日志
        self.logger: Logger = Logger.get_memory_logger()

        # 初始化pipeline
        self.pipeline_list = self.get_pipeline()
        self.print_and_init_worker(self.pipeline_list)

    def get_worker(self, worker_name: str, is_multi_thread: bool = False) -> BaseWorker:
        return init_instance_by_config(
            config = W.get(worker_name),
            try_kwargs={
                "is_multi_thread": is_multi_thread,
                "thread_pool": self.thread_pool
            }
            )

    def worker_run(self, worker_list: list[str]) -> bool:
        for worker_name in worker_list:
            worker = self.worker_dict[worker_name]
            # 执行子类实现的_run函数
            worker.run()
            # 保存worker的运行信息
            self.run_infos.append(worker.run_info_dict)
            # 结束pipeline
            if not worker.continue_run:
                return False
        return True

    @timer
    def print_and_init_worker(self, pipeline_list: list[list]):
        self.logger.info("----- Pipeline Begin -----")
        i: int = 0
        for pipeline_part in pipeline_list:
            if len(pipeline_part) == 1:
                for w in pipeline_part[0]:
                    self.logger.info(f"stage{i}: {w}")
                    self.worker_dict[w] = self.get_worker(w)
                    i += 1
            else:
                for w_zip in zip_longest(*pipeline_part, fillvalue="-"):
                    self.logger.info(f"stage{i}: {' | '.join(w_zip)}")
                    i += 1
                    for w in w_zip:
                        if w == "-":
                            continue
                        self.worker_dict[w] = self.get_worker(w, is_multi_thread=True)
        self.logger.info("----- Pipeline End -----")

    def get_context(self, key: str, default=None) -> Any:
        return self.context_handler.get_context(key, default)

    def flush(self, request: MemoryServiceRequestModel):
        # 全局上下文，worker之间交换参数和变量
        self.context_handler.flush()
    
        # 运行信息
        self.run_infos = []
        self.context_handler.set_context(common_constants.REQUEST, request)
        for pipeline_part in self.pipeline_list:
            pipeline_part.flush(self.context_handler)

    @timer
    def get_pipeline(self) -> list[list]:
        pipeline_str = C.pipeline.get(self.method)
        self.logger.info(f"pipeline={pipeline_str}")

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

    def run(self):
        # run workers in multi threads
        with self.thread_pool, Timer("ALL_PIPELINE"):
            for pipeline_part in self.pipeline_list:
                if len(pipeline_part) == 1:
                    if not self.worker_run(pipeline_part[0]):
                        break
                elif self.max_workers == 1:
                    for worker_list in pipeline_part:
                        self.worker_run(worker_list)
                else:
                    t_list = []
                    for worker_list in pipeline_part:
                        time.sleep(0.001)
                        t_list.append(self.thread_pool.submit(self.worker_run, worker_list))

                    flag = True
                    for future in as_completed(t_list):
                        if not future.result():
                            flag = False
                            break
                    if not flag:
                        break

        # 获取ext_info
        ext_info = self.get_context(RESPONSE_EXT_INFO)
        if ext_info is None:
            ext_info = {}
            self.context_handler.set_context(RESPONSE_EXT_INFO, ext_info)

        # 保存 run_info_list
        ext_info["run_infos"] = json.dumps(self.run_infos, ensure_ascii=False)
