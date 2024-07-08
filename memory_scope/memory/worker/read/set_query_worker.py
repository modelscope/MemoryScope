import datetime

from memory_scope.constants.common_constants import QUERY_WITH_TS
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker


class SetQueryWorker(MemoryBaseWorker):

    def _run(self):
        query = "_"
        query_timestamp = int(datetime.datetime.now().timestamp())

        if "query" in self.chat_kwargs:
            # cli test query
            query = self.chat_kwargs["query"]

        elif self.chat_messages:
            query = self.chat_messages[-1].content
            query_timestamp = self.chat_messages[-1].time_created

        self.set_context(QUERY_WITH_TS, (query, query_timestamp))
