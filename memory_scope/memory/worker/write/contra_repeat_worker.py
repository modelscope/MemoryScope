from typing import List
from memory_scope.constants.common_constants import NEW_OBS_NODES, NEW_OBS_WITH_TIME_NODES, MERGE_OBS_NODES, TODAY_NODES
from memory_scope.constants.language_constants import NONE_WORD, CONTRADICTORY_WORD, INCLUDED_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class ContraRepeatWorker(MemoryBaseWorker):
    """
    The `ContraRepeatWorker` class specializes in processing memory nodes to identify and handle
    contradictory and repetitive information. It extends the base functionality of `MemoryBaseWorker`.

    Responsibilities:
    - Collects observation nodes from various memory categories.
    - Constructs a prompt with these observations for language model analysis.
    - Parses the model's response to detect contradictions or redundancies.
    - Adjusts the status of memory nodes based on the analysis.
    - Persists the updated node statuses back into memory.
    """
    FILE_PATH: str = __file__

    def _run(self):
        """
        Executes the primary routine of the ContraRepeatWorker which involves fetching memory nodes,
        constructing a prompt, querying a language model, parsing the response to identify nodes for merging,
        updating node statuses, and saving the updated nodes back to memory.

        Steps:
        1. Retrieves new observation nodes and nodes observed on the current day.
        2. Optionally combines today's nodes with the new ones, sorts, and limits the list by a predefined count.
        3. Constructs a prompt using the combined nodes, system prompt, and a few-shot example.
        4. Queries a language model with the constructed prompt.
        5. Parses the model's response to identify nodes to merge or exclude based on contradiction or redundancy.
        6. Updates the status of nodes accordingly.
        7. Persists the changes back to memory storage.
        """
        all_obs_nodes: List[MemoryNode] = self.memory_handler.get_memories([NEW_OBS_NODES, NEW_OBS_WITH_TIME_NODES])
        if not all_obs_nodes:
            self.logger.info("all_obs_nodes is empty!")
            self.continue_run = False
            return

        today_obs_nodes: List[MemoryNode] = self.memory_handler.get_memories(TODAY_NODES)

        if today_obs_nodes:
            all_obs_nodes.extend(today_obs_nodes)
        all_obs_nodes = sorted(all_obs_nodes, key=lambda x: x.timestamp, reverse=True)[:self.contra_repeat_max_count]

        # build prompt
        user_query_list = []
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.content}")

        system_prompt = self.prompt_handler.contra_repeat_system.format(num_obs=len(user_query_list),
                                                                        user_name=self.target_name)
        few_shot = self.prompt_handler.contra_repeat_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.contra_repeat_user_query.format(user_query="\n".join(user_query_list),
                                                                         user_name=self.target_name)
        contra_repeat_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"contra_repeat_message={contra_repeat_message}")

        # call LLM
        response = self.generation_model.call(messages=contra_repeat_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response.status or not response.message.content:
            return
        response_text = response.message.content

        # parse text
        idx_merge_obs_list = ResponseTextParser(response_text).parse_v1(self.__class__.__name__)
        if len(idx_merge_obs_list) <= 0:
            self.add_run_info("idx_merge_obs_list is empty!")
            return

        # add merged obs
        merge_obs_nodes: List[MemoryNode] = []
        for obs_content_list in idx_merge_obs_list:
            if not obs_content_list:
                continue

            # Expecting a pair [index, flag]
            if len(obs_content_list) != 2:
                self.logger.warning(f"obs_content_list={obs_content_list} is invalid!")
                continue

            idx, keep_flag = obs_content_list

            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            # index number needs to be corrected to -1
            idx = int(idx) - 1
            if idx >= len(all_obs_nodes):
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            # judge flag
            if keep_flag not in self.get_language_value([NONE_WORD, CONTRADICTORY_WORD, INCLUDED_WORD]):
                self.logger.warning(f"keep_flag={keep_flag} is invalid!")
                continue

            node: MemoryNode = all_obs_nodes[idx]
            if keep_flag != self.get_language_value(NONE_WORD):
                node.status = MemoryNodeStatus.EXPIRED.value
            self.logger.info(f"contra_repeat stage: {node.content} {node.status}")
            merge_obs_nodes.append(node)

        # save context
        self.memory_handler.set_memories(MERGE_OBS_NODES, merge_obs_nodes, log_repeat=False)
