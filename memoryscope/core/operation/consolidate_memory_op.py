from typing import List

from memoryscope.constants.common_constants import CHAT_KWARGS, CHAT_MESSAGES, RESULT, TARGET_NAME, USER_NAME
from memoryscope.core.operation.backend_operation import BackendOperation
from memoryscope.scheme.message import Message


class ConsolidateMemoryOp(BackendOperation):

    def __init__(self,
                 message_lock,
                 contextual_msg_min_count: int = 0,
                 **kwargs):
        super().__init__(**kwargs)
        self.message_lock = message_lock
        self.contextual_msg_min_count: int = contextual_msg_min_count

    def run_operation(self, target_name: str, **kwargs):
        """
        Executes an operation after preparing the chat context, checking message memory status,
        and updating workflow status accordingly.

        If the number of not-memorized messages is less than the contextual message count,
        the operation is skipped. Otherwise, it sets up the chat context, runs the workflow,
        captures the result, and updates the memory status.

        Args:
            target_name (str): target_name(human name).
            **kwargs: Keyword arguments for chat operation configuration.

        Returns:
            Any: The result obtained from running the workflow.
        """

        chat_messages: List[List[Message]] = []
        for messages in self.chat_messages:
            if not messages:
                continue

            if messages[0].memorized:
                continue

            contain_flag = False

            for msg in messages:
                if msg.role_name == target_name:
                    contain_flag = True
                    break

            if contain_flag:
                chat_messages.append(messages)

        if not chat_messages:
            self.logger.info(f"empty not_memorized chat_messages for target_name={target_name}.")
            return

        if len(chat_messages) < self.contextual_msg_min_count:
            self.logger.info(f"not_memorized_size={len(chat_messages)} < {self.contextual_msg_min_count}, skip.")
            return

        # prepare kwargs
        workflow_kwargs = {
            CHAT_MESSAGES: chat_messages,
            CHAT_KWARGS: {**kwargs, **self.kwargs},
            TARGET_NAME: target_name,
            USER_NAME: self.user_name,
        }

        # Execute the workflow with the prepared context
        self.run_workflow(**workflow_kwargs)

        # Retrieve the result from the context after workflow execution
        result = self.workflow_context.get(RESULT)

        # set message memorized
        with self.message_lock:
            for messages in chat_messages:
                for msg in messages:
                    msg.memorized = True

        return result
