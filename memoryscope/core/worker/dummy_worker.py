import datetime

from memoryscope.constants.common_constants import RESULT, WORKFLOW_NAME, CHAT_KWARGS
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker


class DummyWorker(MemoryBaseWorker):
    def _run(self):
        """
        Executes the dummy worker's run logic by logging workflow entry, capturing the current timestamp,
        file path, and setting the result context with details about the workflow execution.

        This method utilizes the BaseWorker's capabilities to interact with the workflow context.
        """
        workflow_name = self.get_context(WORKFLOW_NAME)
        chat_kwargs = self.get_context(CHAT_KWARGS)
        self.logger.info(f"Entering workflow={workflow_name}.dummy_worker!")
        # Records the current timestamp as an integer
        ts = int(datetime.datetime.now().timestamp())
        # Retrieves the current file's path
        file_path = __file__
        self.set_context(RESULT, f"test {workflow_name} kwargs={chat_kwargs} file_path={file_path} \nts={ts}")
