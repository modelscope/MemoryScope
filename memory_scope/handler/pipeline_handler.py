import re
import threading
from concurrent.futures import as_completed
from itertools import zip_longest
from typing import Dict, Any

from memory_scope.enumeration.memory_method_enum import MemoryMethodEnum
from memory_scope.handler.global_context import GLOBAL_CONTEXT
from memory_scope.utils.logger import Logger
from memory_scope.utils.timer import Timer


class PipelineHandler(object):
    def __init__(self, user_name: str, memory_method_type: MemoryMethodEnum, pipeline_str: str):

        self.user_name: str = user_name
        self.memory_method_type: MemoryMethodEnum = memory_method_type
        self.pipeline_str: str = pipeline_str

        # 日志
        self.logger: Logger = Logger.get_logger()

        # pipeline上下文和锁
        self.context: Dict[str, Any] = {}
        self.context_lock = threading.Lock()

        # 解析和打印 pipeline
        self.pipeline_list: list[list] = []
        self._parse_pipeline()
        self._print_pipeline()

    def _parse_pipeline(self):
        # re-match e.g., [a|b],c,[d,e,f|g,h],j
        pattern = r'(\[[^\]]*\]|[^,]+)'
        pipeline_split = re.findall(pattern, self.pipeline_str)

        self.pipeline_list = []
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
            self.pipeline_list.append([x.split(",") for x in line_split])

    def _print_pipeline(self):
        self.logger.info(f"----- {self.user_name} {self.memory_method_type.value} Pipeline Begin -----")
        i: int = 0
        for pipeline_part in self.pipeline_list:
            if len(pipeline_part) == 1:
                for w in pipeline_part[0]:
                    self.logger.info(f"stage{i}: {w}")
                    i += 1
                    GLOBAL_CONTEXT.worker_dict[w].context = self.context
            else:
                for w_zip in zip_longest(*pipeline_part, fillvalue="-"):
                    self.logger.info(f"stage{i}: {' | '.join(w_zip)}")
                    i += 1
                    for w in w_zip:
                        if w == "-":
                            continue
                        GLOBAL_CONTEXT.worker_dict[w].is_multi_thread = True
                        GLOBAL_CONTEXT.worker_dict[w].context_lock = self.context_lock
                        GLOBAL_CONTEXT.worker_dict[w].context = self.context
        self.logger.info(f"----- {self.user_name} {self.memory_method_type.value} Pipeline End -----")

    def get_context(self, key: str, default=None):
        return self.context.get(key, default)

    def clear_context(self):
        self.context.clear()

    @staticmethod
    def worker_run(worker_list: list[str]) -> bool:
        for worker_name in worker_list:
            worker = GLOBAL_CONTEXT.worker_dict[worker_name]
            worker.run()
            if not worker.continue_run:
                return False
        return True

    def run(self):
        with Timer(f"pipeline_{self.user_name}_{self.memory_method_type.value}"):
            for pipeline_part in self.pipeline_list:
                if len(pipeline_part) == 1:
                    if not self.worker_run(pipeline_part[0]):
                        break
                else:
                    t_list = []
                    for worker_list in pipeline_part:
                        t_list.append(GLOBAL_CONTEXT.thread_pool.submit(self.worker_run, worker_list))

                    flag = True
                    for future in as_completed(t_list):
                        if not future.result():
                            flag = False
                            break
                    if not flag:
                        break
