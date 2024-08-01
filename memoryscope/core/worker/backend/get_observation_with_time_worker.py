from typing import List

from memoryscope.constants.common_constants import NEW_OBS_WITH_TIME_NODES
from memoryscope.constants.language_constants import COLON_WORD
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.worker.backend.get_observation_worker import GetObservationWorker
from memoryscope.scheme.message import Message


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
        for msg in self.chat_messages_scatter:
            # Checks if the message content has any time reference words
            if DatetimeHandler.has_time_word(query=msg.content, language=self.language):
                filter_messages.append(msg)
        return filter_messages

    def build_message(self, filter_messages: List[Message]) -> List[Message]:
        """
        Constructs a prompt message for obtaining observations with timestamp information
         based on filtered chat messages.

        This method processes each filtered message with the timestamp information.
        It then organizes these timestamped messages into a structured prompt that includes a system prompt,
        few-shot examples, and the concatenated user queries.

        Args:
            filter_messages (List[Message]): A list of Message objects that have been filtered for processing.

        Returns:
            List[Message]: A list containing the newly constructed Message object for further interaction.
        """
        user_query_list = []
        for i, msg in enumerate(filter_messages):
            # Create a DatetimeHandler instance for each message's timestamp and format it
            dt_handler = DatetimeHandler(dt=msg.time_created)
            dt = dt_handler.string_format(string_format=self.prompt_handler.time_string_format, language=self.language)
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
        get_observation_message_wt = self.prompt_to_msg(system_prompt=system_prompt,
                                                        few_shot=few_shot,
                                                        user_query=user_query)

        # Log the constructed message for debugging purposes
        self.logger.info(f"get_observation_message_wt={get_observation_message_wt}")

        # Return the newly created message
        return get_observation_message_wt
