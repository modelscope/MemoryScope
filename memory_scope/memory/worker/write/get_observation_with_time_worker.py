from typing import List

from memory_scope.constants.common_constants import NEW_OBS_WITH_TIME_NODES
from memory_scope.constants.language_constants import COLON_WORD
from memory_scope.memory.worker.write.get_observation_worker import GetObservationWorker
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.tool_functions import prompt_to_msg


class GetObservationWithTimeWorker(GetObservationWorker):
    """
    A specialized worker class that extends GetObservationWorker functionality to handle
    retrieval of observations which include associated timestamp information from chat messages.
    """
    FILE_PATH: str = __file__
    OBS_STORE_KEY: str = NEW_OBS_WITH_TIME_NODES

    def filter_messages(self) -> List[Message]:
        """
        Filters the chat messages to only include those which contain time-related keywords.

        Returns:
            List[Message]: A list of filtered messages that mention time.
        """
        filter_messages = []
        for msg in self.chat_messages:
            # Checks if the message content has any time reference words
            if DatetimeHandler.has_time_word(query=msg.content):
                filter_messages.append(msg)
        return filter_messages

    def build_message(self, filter_messages: List[Message]) -> List[Message]:
        """
        Constructs a message for obtaining observations with timestamps based on filtered chat messages.

        This method processes each filtered message to append a timestamp formatted per the specified format.
        It then organizes these timestamped queries into a structured prompt that includes a system prompt,
        few-shot examples, and the concatenated user queries, tailored to a target individual with a given language setting.

        Args:
            filter_messages (List[Message]): A list of Message objects that have been filtered for processing.

        Returns:
            List[Message]: A list containing the newly constructed Message object for further interaction.
        """
        user_query_list = []
        for i, msg in enumerate(filter_messages):
            # Create a DatetimeHandler instance for each message's timestamp and format it
            dt_handler = DatetimeHandler(dt=msg.time_created)
            dt = dt_handler.string_format(self.prompt_handler.time_string_format)
            # Append formatted timestamp-query pairs to the user_query_list
            user_query_list.append(f"{i + 1} {dt} {self.target_name}{self.get_language_value(COLON_WORD)}{msg.content}")

        # Construct the system prompt with the count of observations
        system_prompt = self.prompt_handler.get_observation_with_time_system.format(num_obs=len(user_query_list),
                                                                                    user_name=self.target_name)

        # Retrieve the few-shot examples for the prompt
        few_shot = self.prompt_handler.get_observation_with_time_few_shot.format(user_name=self.target_name)

        # Format the user query section with the concatenated list of timestamped queries
        user_query = self.prompt_handler.get_observation_with_time_user_query.format(
            user_query="\n".join(user_query_list),
            user_name=self.target_name)

        # Assemble the final message for observation retrieval
        obtain_obs_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)

        # Log the constructed message for debugging purposes
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")

        # Return the newly created message
        return obtain_obs_message
