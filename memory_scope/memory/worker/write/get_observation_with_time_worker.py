from typing import List

from memory_scope.constants.common_constants import NEW_OBS_WITH_TIME_NODES
from memory_scope.constants.language_constants import DATATIME_WORD_LIST, COLON_WORD
from memory_scope.memory.worker.write.get_observation_worker import GetObservationWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.tool_functions import prompt_to_msg


class GetObservationWithTimeWorker(GetObservationWorker):

    def build_prompt(self) -> List[Message]:
        # build prompt
        user_query_list = []
        i = 1
        for msg in self.chat_messages:
            match = False
            for time_keyword in self.get_language_value(DATATIME_WORD_LIST):
                if time_keyword in msg.content:
                    match = True
                    break
            if match:
                dt_handler = DatetimeHandler(dt=msg.time_created)
                dt = dt_handler.string_format(self.prompt_handler.time_string_format)
                user_query_list.append(f"{i} {dt} {self.target_name}{self.get_language_value(COLON_WORD)}{msg.content}")
                i += 1

        if not user_query_list:
            self.logger.warning(f"get obs_with_time user_query_list={user_query_list} is empty")
            return []

        system_prompt = self.prompt_handler.get_observation_with_time_system.format(num_obs=len(user_query_list),
                                                                                    user_name=self.target_name)
        few_shot = self.prompt_handler.get_observation_with_time_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.get_observation_with_time_user_query.format(
            user_query="\n".join(user_query_list),
            user_name=self.target_name)

        obtain_obs_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")
        return obtain_obs_message

    def save(self, new_obs_nodes: List[MemoryNode]):
        self.set_context(NEW_OBS_WITH_TIME_NODES, new_obs_nodes)
