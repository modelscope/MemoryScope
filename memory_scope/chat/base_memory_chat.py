from abc import ABCMeta, abstractmethod

from memory_scope.constants.common_constants import RELATED_MEMORIES
from memory_scope.enumeration.memory_method_enum import MemoryMethodEnum
from memory_scope.handler.pipeline_handler import PipelineHandler


class BaseMemoryChat(metaclass=ABCMeta):

    def __init__(self,
                 user_name: str,
                 retrieve_pipeline: str,
                 summary_short_pipeline: str,
                 summary_long_pipeline: str,
                 **kwargs):
        self.user_name: str = user_name
        self.retrieve_pipeline_handler = PipelineHandler(user_name=user_name,
                                                         memory_method_type=MemoryMethodEnum.RETRIEVE,
                                                         pipeline_str=retrieve_pipeline)

        self.summary_short_pipeline_handler = PipelineHandler(user_name=user_name,
                                                              memory_method_type=MemoryMethodEnum.SUMMARY_SHORT,
                                                              pipeline_str=summary_short_pipeline)

        self.summary_long_pipeline_handler = PipelineHandler(user_name=user_name,
                                                             memory_method_type=MemoryMethodEnum.SUMMARY_LONG,
                                                             pipeline_str=summary_long_pipeline)

    def retrieve(self):
        self.retrieve_pipeline_handler.run()
        return self.retrieve_pipeline_handler.get_context(RELATED_MEMORIES, [])

    def summary_short(self):
        self.summary_short_pipeline_handler.run()

    def summary_long(self):
        self.summary_long_pipeline_handler.run()

    @abstractmethod
    def chat(self):
        """
        :return:
        """
