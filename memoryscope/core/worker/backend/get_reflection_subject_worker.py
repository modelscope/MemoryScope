from typing import List

from memoryscope.constants.common_constants import NOT_REFLECTED_NODES, INSIGHT_NODES
from memoryscope.constants.language_constants import COMMA_WORD
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.utils.response_text_parser import ResponseTextParser
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.action_status_enum import ActionStatusEnum
from memoryscope.enumeration.memory_type_enum import MemoryTypeEnum
from memoryscope.scheme.memory_node import MemoryNode


class GetReflectionSubjectWorker(MemoryBaseWorker):
    """
    A specialized worker class responsible for retrieving unreflected memory nodes,
    generating reflection prompts with current insights, invoking an LLM for fresh insights,
    parsing the LLM responses, forming new insight nodes, and updating memory statuses accordingly.
    """
    FILE_PATH: str = __file__

    def _parse_params(self, **kwargs):
        self.reflect_obs_cnt_threshold: int = kwargs.get("reflect_obs_cnt_threshold", 10)
        self.generation_model_kwargs: dict = kwargs.get("generation_model_kwargs", {})
        self.reflect_num_questions: int = kwargs.get("reflect_num_questions", 0)

    def new_insight_node(self, insight_key: str) -> MemoryNode:
        """
        Creates a new MemoryNode for an insight with the given key, enriched with current datetime metadata.

        Args:
            insight_key (str): The unique identifier for the insight.

        Returns:
            MemoryNode: A new MemoryNode instance representing the insight, marked as new and of type INSIGHT.
        """
        dt_handler = DatetimeHandler()
        # Prepare metadata with current datetime info
        meta_data = {k: str(v) for k, v in dt_handler.get_dt_info_dict(self.language).items()}

        return MemoryNode(user_name=self.user_name,
                          target_name=self.target_name,
                          meta_data=meta_data,
                          key=insight_key,
                          memory_type=MemoryTypeEnum.INSIGHT.value,
                          action_status=ActionStatusEnum.NEW.value)

    def _run(self):
        """
        Executes the main logic of reflecting on unaudited memory nodes to derive new insights.

        Steps include:
        - Retrieving unaudited memory nodes.
        - Checking the count against a threshold to decide whether to proceed.
        - Compiling a list of existing insight keys.
        - Generating a reflection prompt with system message, few-shot examples, and user queries.
        - Calling the language model for new insights.
        - Parsing the model's responses for new insight keys.
        - Creating new insight nodes and updating the memory status accordingly.
        """
        not_reflected_nodes: List[MemoryNode] = self.memory_manager.get_memories(NOT_REFLECTED_NODES)
        insight_nodes: List[MemoryNode] = self.memory_manager.get_memories(INSIGHT_NODES)

        # Count unaudited nodes
        not_reflected_count = len(not_reflected_nodes)
        if not_reflected_count < self.reflect_obs_cnt_threshold:
            self.logger.info(f"not_reflected_count({not_reflected_count}) < threshold({self.reflect_obs_cnt_threshold})"
                             f" is not enough, skip.")
            # self.continue_run = False
            return

        # Compile existing insight keys
        exist_keys: List[str] = [n.key for n in insight_nodes]
        self.logger.info(f"exist_keys={exist_keys}")

        # Generate reflection prompt components
        user_query_list = [n.content for n in not_reflected_nodes]
        if self.reflect_num_questions > 0:
            num_questions = self.reflect_num_questions
        else:
            num_questions = len(user_query_list)

        system_prompt = self.prompt_handler.get_reflection_subject_system.format(
            user_name=self.target_name,
            num_questions=num_questions)
        few_shot = self.prompt_handler.get_reflection_subject_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.get_reflection_subject_user_query.format(
            user_name=self.target_name,
            exist_keys=self.get_language_value(COMMA_WORD).join(exist_keys),
            user_query="\n".join(user_query_list))

        # Construct and log reflection message
        reflect_message = self.prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"reflect_message={reflect_message}")

        # Invoke Language Model for new insights
        response = self.generation_model.call(messages=reflect_message, **self.generation_model_kwargs)

        # Handle empty response
        if not response.status or not response.message.content:
            return

        # Parse LLM response for new insight keys and update memory
        new_insight_keys = ResponseTextParser(response.message.content, self.language,
                                              self.__class__.__name__).parse_v2()
        if new_insight_keys:
            for insight_key in new_insight_keys:
                self.memory_manager.add_memories(INSIGHT_NODES, self.new_insight_node(insight_key))

        # Mark unaudited nodes as reflected
        for node in not_reflected_nodes:
            node.obs_reflected = 1
            node.action_status = ActionStatusEnum.MODIFIED
