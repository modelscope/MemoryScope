from memory_scope.chat.memory_service import MemoryService
from memory_scope.handler.init_handler import InitHandler


class MemoryChat(object):

    def __init__(self, init_handler: InitHandler):
        self.init_handler: InitHandler = init_handler

        self.memory_service: MemoryService = MemoryService(
            retrieve_pipeline=init_handler.retrieve_pipeline,
            summary_short_pipeline=init_handler.retrieve_pipeline,
            summary_long_pipeline=init_handler.retrieve_pipeline,
        )

    def memory_retrieve(self):
        pass

    def memory_summary_short(self):
        pass

    def memory_summary_long(self):
        pass

    def chat(self):
        pass

    def chat_with_memory(self):
        pass
