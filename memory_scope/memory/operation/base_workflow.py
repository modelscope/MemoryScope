import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import zip_longest
from typing import Dict, Any, List

from memory_scope.constants.common_constants import WORKFLOW_NAME
from memory_scope.memory.worker.base_worker import BaseWorker
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger
from memory_scope.utils.timer import Timer
from memory_scope.utils.tool_functions import init_instance_by_config


class BaseWorkflow(object):

    def __init__(self,
                 name: str,
                 workflow: str,
                 thread_pool: ThreadPoolExecutor = G_CONTEXT.thread_pool,
                 **kwargs):

        self.name: str = name
        self.workflow: str = workflow
        self.thread_pool: ThreadPoolExecutor = thread_pool
        self.kwargs = kwargs

        self.workflow_worker_list: List[List[List[str]]] = []
        self.worker_dict: Dict[str, BaseWorker | bool] = {}
        self.context: Dict[str, Any] = {}
        self.context_lock = threading.Lock()

        self.logger: Logger = Logger.get_logger()

        if self.workflow:
            self.workflow_worker_list = self._parse_workflow()
            self._print_workflow()

    def _parse_workflow(self):
        # re-match e.g., [a|b],c,[d,e,f|g,h],j
        pattern = r'(\[[^\]]*\]|[^,]+)'
        workflow_split = re.findall(pattern, self.workflow)
        for workflow_part in workflow_split:
            # e.g., [d,e,f|g,h]
            workflow_part = workflow_part.strip()
            if '[' in workflow_part or ']' in workflow_part:
                workflow_part = workflow_part.replace('[', '').replace(']', '')

            # e.g., ["d,e,f", "g,h"]
            line_split = [x.strip() for x in workflow_part.split("|") if x]
            if len(line_split) <= 0:
                continue

            # is under multi thread cond
            is_multi_thread: bool = len(line_split) > 1

            # e.g., ["d","e","f"]
            line_split_split: List[List[str]] = []
            for sub_line_split in line_split:
                sub_split = [x.strip() for x in sub_line_split.split(",")]
                line_split_split.append(sub_split)
                # add workers
                for sub_item in sub_split:
                    self.worker_dict[sub_item] = is_multi_thread
            self.workflow_worker_list.append(line_split_split)
        return self.workflow_worker_list

    def _print_workflow(self):
        self.logger.info(f"----- print_workflow_{self.name}_begin -----")
        i: int = 0
        for workflow_part in self.workflow_worker_list:
            if len(workflow_part) == 1:
                for w in workflow_part[0]:
                    self.logger.info(f"stage{i}: {w}")
                    i += 1
            else:
                for w_zip in zip_longest(*workflow_part, fillvalue="-"):
                    self.logger.info(f"stage{i}: {' | '.join(w_zip)}")
                    i += 1
                    for w in w_zip:
                        if w == "-":
                            continue
        self.logger.info(f"----- print_workflow_{self.name}_end -----")

    def init_workers(self, is_backend: bool = False, **kwargs):
        for name in list(self.worker_dict.keys()):
            if name not in G_CONTEXT.worker_config:
                raise RuntimeError(f"worker={name} is not exists in worker_config!")

            self.worker_dict[name] = init_instance_by_config(
                config=G_CONTEXT.worker_config[name],
                suffix_name="worker",
                name=name,
                is_multi_thread=is_backend or self.worker_dict[name],
                context=self.context,
                context_lock=self.context_lock,
                **kwargs)

    def _run_sub_workflow(self, worker_list: List[str]) -> bool:
        for name in worker_list:
            worker = self.worker_dict[name]
            worker.run()
            if not worker.continue_run:
                return False
        return True

    def run_workflow(self):
        with Timer(f"run_workflow_{self.name}"):
            self.context[WORKFLOW_NAME] = self.name
            for workflow_part in self.workflow_worker_list:
                if len(workflow_part) == 1:
                    if not self._run_sub_workflow(workflow_part[0]):
                        break
                else:
                    t_list = []
                    for sub_workflow in workflow_part:
                        t_list.append(G_CONTEXT.thread_pool.submit(self._run_sub_workflow, sub_workflow))

                    flag = True
                    for future in as_completed(t_list):
                        if not future.result():
                            flag = False
                            break
                    if not flag:
                        break
