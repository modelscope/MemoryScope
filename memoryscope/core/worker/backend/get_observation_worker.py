from typing import List

from memoryscope.constants.common_constants import NEW_OBS_NODES, TIME_INFER
from memoryscope.constants.language_constants import REPEATED_WORD, NONE_WORD, COLON_WORD, TIME_INFER_WORD
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.utils.response_text_parser import ResponseTextParser
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.action_status_enum import ActionStatusEnum
from memoryscope.enumeration.memory_type_enum import MemoryTypeEnum
from memoryscope.scheme.memory_node import MemoryNode
from memoryscope.scheme.message import Message


class GetObservationWorker(MemoryBaseWorker):
    """
    A specialized worker class to generate the observations from the original chat histories.
    """
    FILE_PATH: str = __file__
    OBS_STORE_KEY: str = NEW_OBS_NODES

    def _parse_params(self, **kwargs):
        self.generation_model_kwargs: dict = kwargs.get("generation_model_kwargs", {})

    def add_observation(self, message: Message, time_infer: str, obs_content: str, keywords: str):
        """
        Builds a MemoryNode containing the observation details.

        Args:
            message (Message): The source message from which the observation is derived.
            time_infer (str): The inferred time if available.
            obs_content (str): The content of the observation.
            keywords (str): Keywords associated with the observation.

        Returns:
            MemoryNode: The constructed MemoryNode containing the observation.
        """
        dt_handler = DatetimeHandler(dt=message.time_created)

        # build meta data
        meta_data = {
            MemoryTypeEnum.CONVERSATION.value: message.content,
            TIME_INFER: time_infer,
            "keywords": keywords,
            **{k: str(v) for k, v in dt_handler.get_dt_info_dict(self.language).items()},
        }

        if time_infer:
            dt_info_dict = DatetimeHandler.extract_date_parts(input_string=time_infer, language=self.language)
            meta_data.update({f"event_{k}": str(v) for k, v in dt_info_dict.items()})
            obs_content = (f"{obs_content} ({self.get_language_value(TIME_INFER_WORD)}"
                           f"{self.get_language_value(COLON_WORD)} {time_infer})")

        return MemoryNode(user_name=self.user_name,
                          target_name=self.target_name,
                          meta_data=meta_data,
                          content=obs_content,
                          memory_type=MemoryTypeEnum.OBSERVATION.value,
                          action_status=ActionStatusEnum.NEW.value,
                          timestamp=message.time_created)

    def filter_messages(self) -> List[Message]:
        """
        Filters the chat messages to only include those which not contain time-related keywords.

        Returns:
            List[Message]: A list of filtered messages that mention time.
        """
        filter_messages = []
        for msg in self.chat_messages:
            if not DatetimeHandler.has_time_word(query=msg.content, language=self.language):
                filter_messages.append(msg)

        self.logger.info(f"after filter_messages.size from {len(self.chat_messages)} to {len(filter_messages)}")
        return filter_messages

    def build_message(self, filter_messages: List[Message]) -> List[Message]:
        """
        Constructs a formatted message for observation based on input messages, incorporating system prompts,
        few-shot examples, and user queries.

        Args:
            filter_messages (List[Message]): A list of messages filtered for observation processing.

        Returns:
            List[Message]: A list containing the constructed message ready for observation.
        """
        user_query_list = []
        for i, msg in enumerate(filter_messages):
            # Construct each user query item with index, target name, and message content
            user_query_list.append(f"{i + 1} {self.target_name}{self.get_language_value(COLON_WORD)}{msg.content}")

        # Format the system prompt with the number of observations and target name
        system_prompt = self.prompt_handler.get_observation_system.format(num_obs=len(user_query_list),
                                                                          user_name=self.target_name)

        # Incorporate few-shot examples into the prompt with the target name
        few_shot = self.prompt_handler.get_observation_few_shot.format(user_name=self.target_name)

        # Assemble the user query part of the prompt with the list of formatted user queries
        user_query = self.prompt_handler.get_observation_user_query.format(user_query="\n".join(user_query_list),
                                                                           user_name=self.target_name)

        # Combine system prompt, few-shot, and user query into a single message for obtaining observations
        obtain_obs_message = self.prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)

        # Log the constructed observation message
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")

        # Return the processed message(s) for further steps in the observation workflow
        return obtain_obs_message

    def _run(self):
        """
        Processes chat messages to extract observations, inferring timestamps and content relevance,
        and stores the extracted information as MemoryNode objects within the conversation memory.

        Steps:
        1. Filter messages based on predefined criteria.
        2. Constructs a message for the language model to generate observations.
        3. Calls the language model to predict observation details.
        4. Parses the model's response to extract observation lists.
        5. Validates and structures each observed event into MemoryNode objects.
        6. Stores these MemoryNodes in the conversation memory under a specific key.
        """
        # Filters messages and constructs an input message for the language model
        filter_messages = self.filter_messages()
        if not filter_messages:
            self.logger.warning("get obs filter_messages is empty!")
            return

        obtain_obs_message = self.build_message(filter_messages)

        # Generates observations using the language model
        response = self.generation_model.call(messages=obtain_obs_message, **self.generation_model_kwargs)
        if not response.status or not response.message.content:
            return

        response_text = response.message.content

        # Parses the generated text to extract observation indices, times, contents, and keywords
        idx_obs_list = ResponseTextParser(response_text, self.language, self.__class__.__name__).parse_v1()
        if len(idx_obs_list) <= 0:
            self.logger.warning("idx_obs_list is empty!")
            return

        # Processes each extracted observation to create MemoryNode objects
        new_obs_nodes: List[MemoryNode] = []
        for obs_content_list in idx_obs_list:
            if not obs_content_list:
                continue

            # Expected format: [index, time_inference, observation_content, keywords]
            if len(obs_content_list) != 4:
                self.logger.warning(f"obs_content_list={obs_content_list} is invalid!")
                continue

            idx, time_infer, obs_content, keywords = obs_content_list

            # Skips processing if content indicates no meaningful observation
            obs_content = obs_content.lower()
            if obs_content in self.get_language_value([NONE_WORD, REPEATED_WORD]):
                continue

            # Validates index format
            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            time_infer = time_infer.lower()
            if time_infer == self.get_language_value(NONE_WORD):
                time_infer = ""

            # Adjusts index to zero-based and checks validity against filtered messages
            idx = int(idx) - 1
            if idx >= len(filter_messages):
                self.logger.warning(f"idx={idx} is invalid! filter_messages.size={len(filter_messages)}")
                continue

            # Creates a MemoryNode for the validated observation and adds it to the list
            new_obs_nodes.append(self.add_observation(message=filter_messages[idx],
                                                      time_infer=time_infer,
                                                      obs_content=obs_content,
                                                      keywords=keywords))

        # Stores the extracted and structured observations in the conversation memory
        self.memory_manager.set_memories(self.OBS_STORE_KEY, new_obs_nodes)
