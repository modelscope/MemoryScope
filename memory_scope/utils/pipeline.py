import re
import threading
import time
from concurrent.futures import as_completed
from itertools import zip_longest
from typing import Dict, Any, List

from chat.global_context import GLOBAL_CONTEXT
from constants.common_constants import MESSAGES, CHAT_NAME
from enumeration.memory_method_enum import MemoryMethodEnum
from scheme.message import Message
from utils.logger import Logger
from utils.timer import Timer
from worker.base_worker import BaseWorker


class Pipeline(object):
    def __init__(self,
                 chat_name: str,
                 memory_method_type: MemoryMethodEnum,
                 pipeline_str: str,
                 history_msg_count: int = 3,
                 loop_interval_time: int = 300,
                 loop_minimum_count: int = 20):

        self.chat_name: str = chat_name
        self.memory_method_type: MemoryMethodEnum = memory_method_type
        self.pipeline_str: str = pipeline_str
        self.history_msg_count: int = history_msg_count
        self.loop_interval_time: int = loop_interval_time
        self.loop_minimum_count: int = loop_minimum_count

        # pipeline上下文和锁
        self.context: Dict[str, Any] = {}
        self.context_lock = threading.Lock()

        # pipeline run config
        self.loop_switch: bool = False
        self.pipeline_list: list[list] = []
        self.worker_set: set[str] = set()
        self.worker_dict: Dict[str, BaseWorker] = {}
        self.injected: bool = False

        # message list
        self.history_message_list: List[Message] = []
        self.current_message_list: List[Message] = []
        self.message_lock = threading.Lock()

        # 日志
        self.logger: Logger = Logger.get_logger()

        self._parse_pipeline()

    def _parse_pipeline(self):
        if not self.pipeline_str:
            return

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
            line_split_split = []
            for sub_line_split in line_split:
                sub_split = [x.strip() for x in sub_line_split.split(",")]
                line_split_split.append(sub_split)
                # add to workers
                self.worker_set.update(sub_split)
            self.pipeline_list.append(line_split_split)

    def _visit_and_inject_workers(self):
        if self.injected:
            return

        self.worker_dict = GLOBAL_CONTEXT.worker_dict[self.chat_name]

        self.logger.info(f"----- {self.chat_name} {self.memory_method_type.value} Pipeline Begin -----")
        i: int = 0
        for pipeline_part in self.pipeline_list:
            if len(pipeline_part) == 1:
                for w in pipeline_part[0]:
                    self.logger.info(f"stage{i}: {w}")
                    i += 1
                    if w not in self.worker_dict:
                        raise RuntimeError(f"worker={w} is not inited.")
                    # 注入context
                    self.worker_dict[w].set_context_dict(self.context)
            else:
                for w_zip in zip_longest(*pipeline_part, fillvalue="-"):
                    self.logger.info(f"stage{i}: {' | '.join(w_zip)}")
                    i += 1
                    for w in w_zip:
                        if w == "-":
                            continue
                        if w not in self.worker_dict:
                            raise RuntimeError(f"worker={w} is not inited.")

                        # 注入context & lock
                        self.worker_dict[w].set_context_dict(self.context, self.context_lock)

        self.logger.info(f"----- {self.chat_name} {self.memory_method_type.value} Pipeline End -----")
        self.injected = True

    def _worker_run(self, worker_list: list[str]) -> bool:
        for worker_name in worker_list:
            worker = self.worker_dict[worker_name]
            worker.run()
            if not worker.continue_run:
                return False
        return True

    def _run(self):
        self._visit_and_inject_workers()

        with Timer(f"pipeline_{self.chat_name}_{self.memory_method_type.value}"):
            self.context[MESSAGES] = self.history_message_list + self.current_message_list
            self.context[CHAT_NAME] = self.chat_name

            for pipeline_part in self.pipeline_list:
                if len(pipeline_part) == 1:
                    if not self._worker_run(pipeline_part[0]):
                        break
                else:
                    t_list = []
                    for worker_list in pipeline_part:
                        t_list.append(GLOBAL_CONTEXT.thread_pool.submit(self._worker_run, worker_list))

                    flag = True
                    for future in as_completed(t_list):
                        if not future.result():
                            flag = False
                            break
                    if not flag:
                        break

    def _thread_loop(self):
        while self.loop_switch:
            time.sleep(self.loop_interval_time)
            if len(self.current_message_list) < self.loop_minimum_count:
                continue
            self._run()
            self.context.clear()
            self.history_message_list = self.history_message_list.extend(self.current_message_list)[
                                        -self.history_msg_count:]
            with self.message_lock:
                self.current_message_list.clear()

    def start_loop_run(self):
        if not self.loop_switch:
            self.loop_switch = True
            return GLOBAL_CONTEXT.thread_pool.submit(self._thread_loop)

    def run(self, result_key: str = None):
        self._run()

        # 获取result
        result = None
        if result_key:
            result = self.context.get(result_key)
        self.context.clear()

        # 清理 msg
        self.history_message_list = self.history_message_list.extend(self.current_message_list)[
                                    -self.history_msg_count:]
        self.current_message_list.clear()
        return result

    def submit_message(self, message: Message, with_lock=True):
        if with_lock:
            with self.message_lock:
                self.current_message_list.append(message)
        else:
            self.current_message_list.append(message)
