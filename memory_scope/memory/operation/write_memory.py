from typing import List

from memory_scope.constants.common_constants import CHAT_MESSAGES, RESULT, CHAT_KWARGS
from memory_scope.memory.operation.base_backend_operation import BaseBackendOperation
from memory_scope.memory.operation.base_operation import OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class WriteMemory(BaseWorkflow, BaseBackendOperation):
    operation_type: OPERATION_TYPE = "backend"

    def __init__(self,
                 chat_messages: List[Message],
                 his_msg_count: int = 0,
                 message_lock=None,
                 contextual_msg_count: int = 6,
                 **kwargs):

        super().__init__(**kwargs)
        BaseBackendOperation.__init__(self, **kwargs)

        self.chat_messages: List[Message] = chat_messages
        self.his_msg_count: int = his_msg_count
        self.message_lock = message_lock
        self.contextual_msg_count: int = contextual_msg_count

    @property
    def not_memorized_size(self):
        """
        Calculates the count of chat messages that have not been memorized.

        Returns:
            int: The total count of chat messages which are not marked as memorized.
        """
        return sum([not x.memorized for x in self.chat_messages])

    def set_memorized(self):
        if self.message_lock:
            with self.message_lock:
                for msg in self.chat_messages:
                    msg.memorized = True

    def init_workflow(self, **kwargs):
        """
        Initializes the workflow by setting up workers, considering backend-specific parameters.

        Args:
            **kwargs: Additional keyword arguments passed for initializing workers.
        """
        self.init_workers(is_backend=True, **kwargs)

    def _run_operation(self, **kwargs):
        """
        Executes an operation after preparing the chat context, checking message memory status,
        and updating workflow status accordingly.

        If the number of not-memorized messages is less than the contextual message count,
        the operation is skipped. Otherwise, it sets up the chat context, runs the workflow,
        captures the result, and updates the memory status.

        Args:
            **kwargs: Keyword arguments for chat operation configuration.

        Returns:
            Any: The result obtained from running the workflow.
        """
        self.context.clear()
        self.context[CHAT_KWARGS] = kwargs
        not_memorized_size = self.not_memorized_size
        if not_memorized_size < self.contextual_msg_count:
            self.logger.info(f"not_memorized_size={not_memorized_size} < "
                             f"contextual_msg_count={self.contextual_msg_count}, skip.")
            return

        self._operation_status_run = True
        max_count = not_memorized_size + self.his_msg_count
        self.context[CHAT_MESSAGES] = [x.copy(deep=True) for x in self.chat_messages[-max_count:]]
        self.run_workflow()
        result = self.context.get(RESULT)
        self.set_memorized()
        return result
