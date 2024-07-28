import asyncio
from abc import ABCMeta, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

from memoryscope.core.utils.logger import Logger
from memoryscope.core.utils.timer import Timer


class BaseWorker(metaclass=ABCMeta):
    """
    BaseWorker is an abstract class that defines a worker with common functionalities
    for managing tasks and context in both asynchronous and multi-thread environments.
    """

    def __init__(self,
                 name: str,
                 context: Dict[str, Any],
                 context_lock=None,
                 raise_exception: bool = True,
                 is_multi_thread: bool = False,
                 thread_pool: ThreadPoolExecutor = None,
                 **kwargs):
        """
        Initializes the BaseWorker with the provided parameters.

        Args:
            name (str): The name of the worker.
            context (Dict[str, Any]): Shared context dictionary.
            context_lock (optional): Lock for synchronizing access to the context in multithread mode.
            raise_exception (bool, optional): Flag to control whether exceptions should be raised.
            is_multi_thread (bool, optional): Flag indicating if the worker operates in multithread mode.
            thread_pool (ThreadPoolExecutor, optional): Thread pool executor for managing multithread tasks.
            kwargs: Additional keyword arguments.
        """

        self.name: str = name
        self.context: Dict[str, Any] = context
        self.context_lock = context_lock
        self.raise_exception: bool = raise_exception
        self.is_multi_thread: bool = is_multi_thread
        self.thread_pool: ThreadPoolExecutor = thread_pool
        self.kwargs: dict = kwargs

        self.continue_run: bool = True
        self.async_task_list: list = []
        self.thread_task_list: list = []
        self.logger: Logger = Logger.get_logger()

        self._parse_params(**kwargs)

    def _parse_params(self, **kwargs):
        """
        Placeholder method for parsing additional parameters.

        Args:
            kwargs: Additional keyword arguments.
        """
        pass

    def submit_async_task(self, fn, *args, **kwargs):
        """
        Submits an asynchronous task to the worker.

        Args:
            fn (callable): The function to be executed.
            args: Positional arguments for the function.
            kwargs: Keyword arguments for the function.

        Raises:
            RuntimeError: If called in multithread mode.
        """
        if self.is_multi_thread:
            raise RuntimeError(f"async_task is not allowed in multi_thread condition")

        self.async_task_list.append((fn, args, kwargs))

    async def _async_gather(self):
        """
        Gathers results of all submitted asynchronous tasks.

        Returns:
            A list of results from the asynchronous tasks.
        """
        return await asyncio.gather(*[fn(*args, **kwargs) for fn, args, kwargs in self.async_task_list])

    def gather_async_result(self):
        """
        Executes all asynchronous tasks and gathers their results.

        Returns:
            A list of results from the asynchronous tasks.

        Raises:
            RuntimeError: If called in multithread mode.
        """
        if self.is_multi_thread:
            raise RuntimeError(f"async_task is not allowed in multi_thread condition")

        results = asyncio.run(self._async_gather())
        self.async_task_list.clear()
        return results

    def submit_thread_task(self, fn, *args, **kwargs):
        """
        Submits a task to be executed in a separate thread.

        Args:
            fn (callable): The function to be executed.
            args: Positional arguments for the function.
            kwargs: Keyword arguments for the function.
        """
        self.thread_task_list.append(self.thread_pool.submit(fn, *args, **kwargs))

    def gather_thread_result(self):
        """
        Gathers results of all submitted multithread tasks.

        Yields:
            The result of each completed task.
        """
        for future in as_completed(self.thread_task_list):
            yield future.result()
        self.thread_task_list.clear()

    @abstractmethod
    def _run(self):
        """
        Abstract method representing the main run logic of the worker that needs to be implemented by subclasses.

        Raises:
            NotImplementedError: If the method is not implemented by the subclass.
        """
        raise NotImplementedError

    def run(self):
        """
        Executes the worker's main logic and manages execution flow and exception handling.

        Uses a Timer to log the execution time of the worker.
        """
        with Timer(f"worker.{self.name}", time_log_type="wrap"):
            self.continue_run = True
            self.async_task_list.clear()
            self.thread_task_list.clear()

            if self.raise_exception:
                self._run()
            else:
                try:
                    self._run()
                except Exception as e:
                    self.logger.exception(f"run {self.name} failed! args={e.args}")

    def get_context(self, key: str, default=None):
        """
        Retrieves a value from the shared context.

        Args:
            key (str): The key for the context value.
            default (optional): Default value if the key is not found.

        Returns:
            The value from the context or the default value.
        """
        return self.context.get(key, default)

    def set_context(self, key: str, value: Any):
        """
        Sets a value in the shared context.

        Args:
            key (str): The key for the context value.
            value (Any): The value to be set.
        """
        if self.is_multi_thread:
            with self.context_lock:
                self.context[key] = value
        else:
            self.context[key] = value

    def has_content(self, key: str):
        """
        Checks if the context contains a specific key.

        Args:
            key (str): The key to check in the context.

        Returns:
            bool: True if the key is in the context, otherwise False.
        """
        return key in self.context
