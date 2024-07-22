from memory_scope.constants.common_constants import CHAT_KWARGS, CHAT_MESSAGES, RESULT
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.operation.backend_operation import BackendOperation


class WriteMemoryOp(BackendOperation):

    def __init__(self, **kwargs):
        super(WriteMemoryOp, self).__init__(**kwargs)

        self.message_lock = kwargs.get("message_lock", None)
        self.contextual_msg_min_count: int = kwargs.get("contextual_msg_min_count", 0)

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

        if not self.chat_messages:
            return

        # Use shallow copy to prevent adding new messages.
        chat_messages = self.chat_messages.copy()

        # filter for user-assistant pair
        if chat_messages[-1].role == MessageRoleEnum.USER.value:
            chat_messages = chat_messages[:-1]

        not_memorized_size = sum([not x.memorized for x in chat_messages])
        if not_memorized_size < self.contextual_msg_min_count:
            self.logger.info(f"not_memorized_size({not_memorized_size}) < "
                             f"contextual_msg_min_count({self.contextual_msg_min_count}), skip.")
            return

        self.context.clear()

        # Add additional arguments to the context
        kwargs.update(**self.kwargs)
        self.context[CHAT_KWARGS] = kwargs

        # Include the most recent messages in the operation context
        self.context[CHAT_MESSAGES] = chat_messages

        # Execute the workflow with the prepared context
        self.run_workflow()

        # Retrieve the result from the context after workflow execution
        result = self.context.get(RESULT)

        # set message memorized
        with self.message_lock:
            for message in chat_messages:
                message.memorized = True

        return result
