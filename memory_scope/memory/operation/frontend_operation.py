from typing import List

from memory_scope.constants.common_constants import RESULT, CHAT_MESSAGES, CHAT_KWARGS
from memory_scope.memory.operation.base_operation import BaseOperation, OPERATION_TYPE
from memory_scope.memory.operation.base_workflow import BaseWorkflow
from memory_scope.scheme.message import Message


class FrontendOperation(BaseWorkflow, BaseOperation):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self,
                 name: str,
                 description: str,
                 chat_messages: List[Message],
                 his_msg_count: int = 0,  # supplement to the current query
                 **kwargs):
        super().__init__(name=name, **kwargs)
        BaseOperation.__init__(self, name=name, description=description)

        self.chat_messages: List[Message] = chat_messages
        self.his_msg_count: int = his_msg_count

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
        self.context.clear()  # Clear the previous operation context
        max_count = 1 + self.his_msg_count  # Determine the number of historical messages to include
        # Include the most recent messages in the operation context
        self.context[CHAT_MESSAGES] = [x.copy(deep=True) for x in self.chat_messages[-max_count:]]
        self.context[CHAT_KWARGS] = kwargs  # Add additional arguments to the context
        self.run_workflow()  # Execute the workflow with the prepared context
        result = self.context.get(RESULT)  # Retrieve the result from the context after workflow execution
        return result
