from typing import List

from memoryscope.constants.common_constants import RESULT, CHAT_MESSAGES, CHAT_KWARGS, TARGET_NAME, USER_NAME
from memoryscope.core.operation.base_operation import BaseOperation, OPERATION_TYPE
from memoryscope.core.operation.base_workflow import BaseWorkflow
from memoryscope.scheme.message import Message


class FrontendOperation(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self,
                 name: str,
                 user_name: str,
                 target_names: List[str],
                 chat_messages: List[List[Message]],
                 description: str,
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self,
                               name=name,
                               user_name=user_name,
                               target_names=target_names,
                               chat_messages=chat_messages,
                               description=description)

    def init_workflow(self, **kwargs):
        """
        Initializes the workflow by setting up workers with provided keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments to be passed during worker initialization.
        """
        self.init_workers(**kwargs)

    def run_operation(self, target_name: str, **kwargs):
        """
        Executes the main operation of reading recent chat messages, initializing workflow,
        and returning the result of the workflow execution.

        Args:
            target_name (str): target_name(human name).
            **kwargs: Additional keyword arguments used in the operation context.

        Returns:
            Any: The result obtained from executing the workflow.
        """

        # prepare kwargs
        workflow_kwargs = {
            CHAT_MESSAGES: self.chat_messages,
            CHAT_KWARGS: {**kwargs, **self.kwargs},
            TARGET_NAME: target_name,
            USER_NAME: self.user_name,
        }

        # Execute the workflow with the prepared context
        self.run_workflow(**workflow_kwargs)

        # Retrieve the result from the context after workflow execution
        return self.workflow_context.get(RESULT)
