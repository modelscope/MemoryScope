from memory_scope.constants.common_constants import RELATED_MEMORIES
from memory_scope.enumeration.memory_method_enum import MemoryMethodEnum
from memory_scope.scheme.message import Message
from memory_scope.utils.pipeline import Pipeline


class MemoryService(object):

    def __init__(self,
                 chat_name: str,
                 retrieve_pipeline: str,
                 retrieve_all_pipeline: str,
                 summary_short_pipeline: str,
                 summary_long_pipeline: str,
                 summary_short_interval_time: int = 60,
                 summary_short_minimum_count: int = 5,
                 summary_long_interval_time: int = 60 * 5,
                 summary_long_minimum_count: int = 5 * 5,
                 **kwargs):
        self.retrieve_pipeline = Pipeline(chat_name=chat_name,
                                          memory_method_type=MemoryMethodEnum.RETRIEVE,
                                          pipeline_str=retrieve_pipeline)

        self.retrieve_all_pipeline = Pipeline(chat_name=chat_name,
                                              memory_method_type=MemoryMethodEnum.RETRIEVE_ALL,
                                              pipeline_str=retrieve_all_pipeline)

        self.summary_short_pipeline = Pipeline(chat_name=chat_name,
                                               memory_method_type=MemoryMethodEnum.SUMMARY_SHORT,
                                               pipeline_str=summary_short_pipeline,
                                               loop_interval_time=summary_short_interval_time,
                                               loop_minimum_count=summary_short_minimum_count)

        self.summary_long_pipeline = Pipeline(chat_name=chat_name,
                                              memory_method_type=MemoryMethodEnum.SUMMARY_LONG,
                                              pipeline_str=summary_long_pipeline,
                                              loop_interval_time=summary_long_interval_time,
                                              loop_minimum_count=summary_long_minimum_count)

        self.kwargs = kwargs

    def retrieve(self, message: Message):
        self.retrieve_pipeline.submit_message(message, with_lock=False)
        self.summary_short_pipeline.submit_message(message)
        self.summary_long_pipeline.submit_message(message)
        return self.retrieve_pipeline.run(RELATED_MEMORIES)

    def retrieve_all(self):
        return self.retrieve_all_pipeline.run(RELATED_MEMORIES)

    def start_memory_backend(self):
        self.summary_short_pipeline.start_loop_run()
        self.summary_long_pipeline.start_loop_run()

    def get_worker_list(self) -> list:
        worker_set = set()
        worker_set.update(self.retrieve_pipeline.worker_set)
        worker_set.update(self.retrieve_all_pipeline.worker_set)
        worker_set.update(self.summary_short_pipeline.worker_set)
        worker_set.update(self.summary_long_pipeline.worker_set)
        return sorted(worker_set)
