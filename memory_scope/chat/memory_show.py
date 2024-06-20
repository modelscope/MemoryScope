from memory_scope.chat.base_memory_chat import BaseMemoryChat


class MemoryShow(BaseMemoryChat):

    def chat_with_memory(self, query: str):
        raise NotImplementedError

    def run(self):
        self.memory_service.start_memory_backend()
        result = self.memory_service.retrieve_all()
        print(result)
