from memory_scope.constants.common_constants import RELATED_MEMORIES
from memory_scope.enumeration.memory_method_enum import MemoryMethodEnum
from memory_scope.handler.pipeline_handler import PipelineHandler
from memory_scope.node.message import Message


class MemoryService(object):

    def __init__(self,
                 user_name: str,
                 retrieve_pipeline: str,
                 retrieve_all_pipeline: str,
                 summary_short_pipeline: str,
                 summary_long_pipeline: str,
                 summary_short_interval_time: int = 60,
                 summary_short_minimum_count: int = 5,
                 summary_long_interval_time: int = 60 * 5,
                 summary_long_minimum_count: int = 5 * 5,
                 **kwargs):
        self.retrieve_pipeline_handler = PipelineHandler(user_name=user_name,
                                                         memory_method_type=MemoryMethodEnum.RETRIEVE,
                                                         pipeline_str=retrieve_pipeline)

        self.retrieve_all_pipeline_handler = PipelineHandler(user_name=user_name,
                                                             memory_method_type=MemoryMethodEnum.RETRIEVE_ALL,
                                                             pipeline_str=retrieve_all_pipeline)

        self.summary_short_pipeline_handler = PipelineHandler(user_name=user_name,
                                                              memory_method_type=MemoryMethodEnum.SUMMARY_SHORT,
                                                              pipeline_str=summary_short_pipeline,
                                                              loop_interval_time=summary_short_interval_time,
                                                              loop_minimum_count=summary_short_minimum_count)

        self.summary_long_pipeline_handler = PipelineHandler(user_name=user_name,
                                                             memory_method_type=MemoryMethodEnum.SUMMARY_LONG,
                                                             pipeline_str=summary_long_pipeline,
                                                             loop_interval_time=summary_long_interval_time,
                                                             loop_minimum_count=summary_long_minimum_count)

        self.kwargs = kwargs

    def retrieve(self, message: Message):
        self.retrieve_pipeline_handler.submit_message(message, with_lock=False)
        self.summary_short_pipeline_handler.submit_message(message)
        self.summary_long_pipeline_handler.submit_message(message)
        return self.retrieve_pipeline_handler.run(RELATED_MEMORIES)

    def retrieve_all(self):
        return self.retrieve_all_pipeline_handler.run(RELATED_MEMORIES)

    def start_summary_short_backend(self):
        self.summary_short_pipeline_handler.start_loop_run()

    def start_summary_long_backend(self):
        self.summary_long_pipeline_handler.start_loop_run()
