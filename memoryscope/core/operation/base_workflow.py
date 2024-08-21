import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import zip_longest
from typing import Dict, Any, List
from rich.console import Console

from memoryscope.constants.common_constants import WORKFLOW_NAME
from memoryscope.core.memoryscope_context import MemoryscopeContext
from memoryscope.core.utils.logger import Logger
from memoryscope.core.utils.timer import Timer
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.core.worker.base_worker import BaseWorker

class BaseWorkflow(object):

    def __init__(self,
                 name: str,
                 memoryscope_context: MemoryscopeContext,
                 workflow: str = "",
                 **kwargs):

        self.name: str = name
        self.memoryscope_context: MemoryscopeContext = memoryscope_context
        self.thread_pool: ThreadPoolExecutor = self.memoryscope_context.thread_pool
        self.workflow: str = workflow
        self.kwargs = kwargs

        self.workflow_worker_list: List[List[List[str]]] = []
        self.worker_dict: Dict[str, BaseWorker | bool] = {}
        self.workflow_context: Dict[str, Any] = {}
        self.context_lock = threading.Lock()

        self.logger: Logger = Logger.get_logger("workflow")

        if self.workflow:
            self.workflow_worker_list = self._parse_workflow()
            self._print_workflow()

    def workflow_print_console(self, *args, **kwargs):
        if self.memoryscope_context.print_workflow_dynamic:
            Console().print(*args, **kwargs)
        return

    def _parse_workflow(self):
        """
        Parses the workflow string to configure worker threads and organizes them into execution order.

        The workflow string format supports complex configurations with optional multi-threading indications.
        E.g., `[task1,task2|task3],task4` denotes task1 and task2 can run in parallel to task3, followed by task4.

        Returns:
            List[List[List[str]]]: A nested list representing the execution plan, including parallel groups and tasks.
        """
        # Regular expression to match components of the workflow, handling both plain items and grouped items.
        pattern = r"(\[[^\]]*\]|[^,]+)"
        # Find all matches in the workflow string based on the pattern.
        workflow_split = re.findall(pattern, self.workflow)

        for workflow_part in workflow_split:
            # e.g., [d,e,f|g,h]
            workflow_part = workflow_part.strip()
            if '[' in workflow_part or ']' in workflow_part:
                workflow_part = workflow_part.replace('[', '').replace(']', '')

            # Split the part by '|' to identify potential parallel task groups.
            line_split = [x.strip() for x in workflow_part.split("|") if x]

            # Skip if no valid tasks are identified after splitting.
            if len(line_split) <= 0:
                continue

            # Determine if the current part involves multi-threading based on the number of groups.
            is_multi_thread: bool = len(line_split) > 1

            # e.g., ["d","e","f"]
            line_split_split: List[List[str]] = []
            for sub_line_split in line_split:
                sub_split = [x.strip() for x in sub_line_split.split(",")]
                line_split_split.append(sub_split)
                # add workers
                for sub_item in sub_split:
                    self.worker_dict[sub_item] = is_multi_thread

            # Append the parsed and structured tasks to the workflow execution plan.
            self.workflow_worker_list.append(line_split_split)

        # Return the fully constructed workflow execution plan.
        return self.workflow_worker_list

    def _print_workflow(self):
        """
        Prints the workflow stages in a structured format. Each stage of the workflow
        is detailed with its constituent parts, either single elements or grouped
        elements separated by ' | '.

        The method iterates over the workflow parts, handling both singular steps
        and parallel steps (where elements are zipped together).
        """
        self.logger.info(f"----- workflow.{self.name}.print.begin -----")
        i: int = 0
        for workflow_part in self.workflow_worker_list:
            if len(workflow_part) == 1:
                # Handles workflow parts with single elements
                for w in workflow_part[0]:
                    self.logger.info(f"stage{i}: {w}")
                    i += 1
            else:
                # Handles workflow parts with multiple parallel elements (zipped)
                for w_zip in zip_longest(*workflow_part, fillvalue="-"):
                    self.logger.info(f"stage{i}: {' | '.join(w_zip)}")
                    i += 1
                    # Skips placeholder '-' used for uneven lists in zip_longest
                    for w in w_zip:
                        if w == "-":
                            continue
        self.logger.info(f"----- workflow.{self.name}.print.end -----")

    def init_workers(self, is_backend: bool = False, **kwargs):
        """
        Initializes worker instances based on the configuration for each worker defined in `G_CONTEXT.worker_config`.
        Each worker can be set to run in a multithreaded mode depending on the `is_backend` flag or the worker's
        individual configuration.

        Args:
            is_backend (bool, optional): A flag indicating whether the workers should be initialized in a
            backend context. Defaults to False.
            **kwargs: Additional keyword arguments to be passed during worker initialization.

        Raises:
            RuntimeError: If a worker mentioned in `self.worker_dict` does not exist in `G_CONTEXT.worker_config`.

        Note:
            This method modifies `self.worker_dict` in-place, replacing the keys with actual worker instances.
        """
        for name in list(self.worker_dict.keys()):
            if name not in self.memoryscope_context.worker_conf_dict:
                raise RuntimeError(f"worker={name} is not exists in worker config!")

            # note: shared context object in all workers
            self.worker_dict[name] = init_instance_by_config(
                config=self.memoryscope_context.worker_conf_dict[name],
                name=name,
                is_multi_thread=is_backend or self.worker_dict[name],
                context=self.workflow_context,
                memoryscope_context=self.memoryscope_context,
                context_lock=self.context_lock,
                thread_pool=self.thread_pool,
                **kwargs)

    def _run_sub_workflow(self, worker_list: List[str]) -> bool:
        for name in worker_list:
            worker = self.worker_dict[name]
            worker.run()
            if not worker.continue_run:
                self.logger.warning(f"worker={worker.name} stop workflow!")
                return False
        return True

    def run_workflow(self, **kwargs):
        """
        Executes the workflow by orchestrating the steps defined in `self.workflow_worker_list`.
        This method supports both sequential and parallel execution of sub-workflows based on the structure
        of `self.workflow_worker_list`.

        If a workflow part consists of a single item, it is executed sequentially. For parts with multiple items,
        they are submitted for parallel execution using a thread pool. The workflow will stop if any sub-workflow
        returns False.

        Args:
            **kwargs: Additional keyword arguments to be passed to context.
        """
        with Timer(f"workflow.{self.name}", time_log_type="wrap"):
            log_buf = f"Operation: {self.name}"
            self.logger.info(log_buf)
            self.workflow_print_console(log_buf, style="bold red")
            self.workflow_context.clear()
            self.workflow_context.update({WORKFLOW_NAME: self.name, **kwargs})
            n_stage = len(self.workflow_worker_list)
            # Iterate over each part of the workflow
            for index, workflow_part in enumerate(self.workflow_worker_list):
                # self.logger.info(self.logger.format_current_context(self.workflow_context))
                # Sequential execution for single-item parts
                if len(workflow_part) == 1:
                    log_buf = f"\t- Operation: {self.name} | {index+1}/{n_stage}: {workflow_part[0]}"
                    self.logger.info(log_buf)
                    self.workflow_print_console(log_buf, style="bold red")
                    if not self._run_sub_workflow(workflow_part[0]):
                        break
                # Parallel execution for multi-item parts
                else:
                    t_list = []
                    # Submit tasks to the thread pool
                    n_sub_stage = len(workflow_part)
                    for sub_index, sub_workflow in enumerate(workflow_part):
                        log_buf = f"\t- Operation: {self.name} | {index+1}/{n_stage} | sub workflow {sub_index+1}/{n_sub_stage}: {str(sub_workflow)}"
                        self.logger.info(log_buf)
                        self.workflow_print_console(log_buf, style="red")
                        t_list.append(self.thread_pool.submit(self._run_sub_workflow, sub_workflow))

                    # Check results; if any task returns False, stop the workflow
                    flag = True
                    for future in as_completed(t_list):
                        if not future.result():
                            flag = False
                    if not flag:
                        break
