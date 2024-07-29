from typing import List

from memoryscope.constants.common_constants import RESULT, CHAT_MESSAGES, CHAT_KWARGS
from memoryscope.core.operation.base_operation import BaseOperation, OPERATION_TYPE
from memoryscope.core.operation.base_workflow import BaseWorkflow
from memoryscope.scheme.message import Message


class FrontendOperation(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self,
                 name: str,
                 description: str,
                 chat_messages: List[Message],
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)

        self.chat_messages: List[Message] = chat_messages

    def init_workflow(self, **kwargs):
        """
        Initializes the workflow by setting up workers with provided keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments to be passed during worker initialization.
        """
        self.init_workers(**kwargs)

    def run_operation(self, **kwargs):
        """
        Executes the main operation of reading recent chat messages, initializing workflow, 
        and returning the result of the workflow execution.

        Args:
            **kwargs: Additional keyword arguments used in the operation context.

        Returns:
            Any: The result obtained from executing the workflow.
        """

        # prepare kwargs
        workflow_kwargs = {
            CHAT_MESSAGES: self.chat_messages,
            CHAT_KWARGS: {**kwargs, **self.kwargs},
        }

        # Execute the workflow with the prepared context
        self.run_workflow(**workflow_kwargs)

        # Retrieve the result from the context after workflow execution
        return self.context.get(RESULT)
