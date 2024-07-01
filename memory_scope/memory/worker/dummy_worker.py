import datetime

from memory_scope.constants.common_constants import RESULT, WORKFLOW_NAME, CHAT_KWARGS
from memory_scope.memory.worker.base_worker import BaseWorker


class DummyWorker(BaseWorker):
    def _run(self):
        workflow_name = self.get_context(WORKFLOW_NAME)
        chat_kwargs = self.get_context(CHAT_KWARGS)
        self.logger.info(f"enter workflow={workflow_name}.dummy_worker!")
        ts = int(datetime.datetime.now().timestamp())
        file_path = __file__
        self.set_context(RESULT, f"test {workflow_name} kwargs={chat_kwargs} file_path={file_path} \nts={ts}")
