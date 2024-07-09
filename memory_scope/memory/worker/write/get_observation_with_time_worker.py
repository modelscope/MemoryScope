from typing import List

from memory_scope.constants.common_constants import NEW_OBS_WITH_TIME_NODES
from memory_scope.constants.language_constants import COLON_WORD
from memory_scope.memory.worker.write.get_observation_worker import GetObservationWorker
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.tool_functions import prompt_to_msg


class GetObservationWithTimeWorker(GetObservationWorker):
    FILE_PATH: str = __file__
    OBS_STORE_KEY: str = NEW_OBS_WITH_TIME_NODES

    def filter_messages(self) -> List[Message]:
        filter_messages = []
        for msg in self.chat_messages:
            if DatetimeHandler.has_time_word(query=msg.content):
                filter_messages.append(msg)
        return filter_messages

    def build_message(self, filter_messages: List[Message]) -> List[Message]:
        user_query_list = []
        for i, msg in enumerate(filter_messages):
            dt_handler = DatetimeHandler(dt=msg.time_created)
            dt = dt_handler.string_format(self.prompt_handler.time_string_format)
            user_query_list.append(f"{i} {dt} {self.target_name}{self.get_language_value(COLON_WORD)}{msg.content}")

        system_prompt = self.prompt_handler.get_observation_with_time_system.format(num_obs=len(user_query_list),
                                                                                    user_name=self.target_name)
        few_shot = self.prompt_handler.get_observation_with_time_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.get_observation_with_time_user_query.format(
            user_query="\n".join(user_query_list),
            user_name=self.target_name)

        obtain_obs_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")
        return obtain_obs_message
