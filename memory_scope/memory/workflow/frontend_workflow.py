from memory_scope.constants.common_constants import RESULT, CHAT_MESSAGES
from memory_scope.memory.workflow.base_workflow import BaseWorkflow


class FrontendWorkflow(BaseWorkflow):

    def run_workflow(self):
        self.context[CHAT_MESSAGES] = self.chat_messages[:1 + self.max_history_message_count]
        self.__call__()
        result = self.context.get(RESULT)
        self.context.clear()
        return result
