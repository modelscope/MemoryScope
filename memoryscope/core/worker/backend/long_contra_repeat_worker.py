from typing import List, Dict

from memoryscope.constants.common_constants import NOT_UPDATED_NODES, MERGE_OBS_NODES
from memoryscope.constants.language_constants import NONE_WORD, CONTAINED_WORD, CONTRADICTORY_WORD
from memoryscope.core.utils.response_text_parser import ResponseTextParser
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.action_status_enum import ActionStatusEnum
from memoryscope.enumeration.memory_type_enum import MemoryTypeEnum
from memoryscope.enumeration.store_status_enum import StoreStatusEnum
from memoryscope.scheme.memory_node import MemoryNode


class LongContraRepeatWorker(MemoryBaseWorker):
    """
    Manages and updates memory entries within a conversation scope by identifying
    and handling contradictions or redundancies. It extends the base MemoryBaseWorker
    to provide specialized functionality for long conversations with potential
    contradictory or repetitive statements.
    """
    FILE_PATH: str = __file__

    def _parse_params(self, **kwargs):
        self.unit_test_flag = False
        self.long_contra_repeat_top_k: int = kwargs.get("long_contra_repeat_top_k", 2)
        self.long_contra_repeat_threshold: float = kwargs.get("long_contra_repeat_threshold", 0.1)
        self.generation_model_kwargs: dict = kwargs.get("generation_model_kwargs", {})
        self.enable_long_contra_repeat: bool = self.memoryscope_context.meta_data["enable_long_contra_repeat"]

    def retrieve_similar_content(self, node: MemoryNode) -> (MemoryNode, List[MemoryNode]):
        """
        Retrieves memory nodes with content similar to the given node, filtering by user/target/status/memory_type.
        Only returns nodes whose similarity score meets or exceeds the predefined threshold.

        Args:
            node (MemoryNode): The reference node used to find similar content in memory.

        Returns:
            Tuple[MemoryNode, List[MemoryNode]]: A tuple containing the original node and a list of similar nodes
            that passed the similarity threshold.
        """
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "store_status": StoreStatusEnum.VALID.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value]
        }
        # Retrieve memories similar to the node's content, limited by top_k and filtered by filter_dict
        retrieve_nodes = self.memory_store.retrieve_memories(query=node.content,
                                                             top_k=self.long_contra_repeat_top_k,
                                                             filter_dict=filter_dict)
        # Filter retrieved nodes based on the similarity threshold
        return node, [n for n in retrieve_nodes if n.score_recall >= self.long_contra_repeat_threshold]

    def _run(self):
        """
        Executes the primary routine of the LongContraRepeatWorker. This involves:
        1. Retrieve not updated memory nodes.
        2. Gather similar content for these nodes.
        3. Organize observed nodes and generating a prompt for the language model.
        4. Call the language model to judge the contradictions or redundancies in retrieved memories.
        5. Parse the model's response to update memory node statuses.
        6. Save the modified memory nodes.

        The process helps in maintaining conversation coherence by resolving contradictions and redundancies.
        """
        if not self.enable_long_contra_repeat:
            self.logger.warning("long_contra_repeat is not enabled!")
            return

        not_updated_nodes: List[MemoryNode] = self.memory_manager.get_memories(NOT_UPDATED_NODES)
        for node in not_updated_nodes:
            self.submit_thread_task(fn=self.retrieve_similar_content, node=node)

        if self.unit_test_flag:
            all_obs_nodes: List[MemoryNode] = not_updated_nodes
        else:
            obs_node_dict: Dict[str, MemoryNode] = {}
            for origin_node, retrieve_nodes in self.gather_thread_result():
                if not retrieve_nodes:
                    continue
                obs_node_dict[origin_node.memory_id] = origin_node
                for node in retrieve_nodes:
                    if node.memory_id in obs_node_dict:
                        continue
                    obs_node_dict[node.memory_id] = node
            all_obs_nodes: List[MemoryNode] = sorted(obs_node_dict.values(), key=lambda x: x.timestamp, reverse=True)

        if not all_obs_nodes:
            self.logger.warning("all_obs_nodes is empty, stop.")
            return

        if len(all_obs_nodes) == 1:
            self.logger.info("all_obs_nodes.size=1, stop.")
            return

        # gene prompt
        user_query_list = []
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.content}")
        system_prompt = self.prompt_handler.long_contra_repeat_system.format(num_obs=len(user_query_list),
                                                                             user_name=self.target_name)
        few_shot = self.prompt_handler.long_contra_repeat_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.long_contra_repeat_user_query.format(user_query="\n".join(user_query_list))

        long_contra_repeat_message = self.prompt_to_msg(system_prompt=system_prompt,
                                                        few_shot=few_shot,
                                                        user_query=user_query)
        self.logger.info(f"long_contra_repeat_message={long_contra_repeat_message}")

        # Invokes the language model for processing the constructed prompt
        response = self.generation_model.call(messages=long_contra_repeat_message, **self.generation_model_kwargs)

        # Handles the case where the model's response is empty
        if not response or not response.message.content:
            return

        # Parses the model's response text to identify updates for memory nodes
        idx_obs_info_list = ResponseTextParser(response.message.content, self.language,
                                               self.__class__.__name__).parse_v1()
        if len(idx_obs_info_list) <= 0:
            self.logger.warning("idx_obs_info_list is empty!")
            return

        # Processes parsed information to update memory nodes' statuses
        merge_obs_nodes: List[MemoryNode] = []
        for idx_obs_info in idx_obs_info_list:
            if not idx_obs_info:
                continue

            if len(idx_obs_info) != 3:
                self.logger.warning(f"idx_obs_info={idx_obs_info} is invalid!")
                continue
            idx, status, content = idx_obs_info

            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            idx = int(idx) - 1
            if idx >= len(all_obs_nodes):
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            status = status.lower()
            if status not in self.get_language_value([CONTRADICTORY_WORD, CONTAINED_WORD, NONE_WORD]):
                self.logger.warning(f"status={status} is invalid!")
                continue

            node: MemoryNode = all_obs_nodes[idx]
            if status == self.get_language_value(CONTRADICTORY_WORD):
                if not content:
                    node.store_status = StoreStatusEnum.EXPIRED.value
                else:
                    node.content = content
                    node.action_status = ActionStatusEnum.CONTENT_MODIFIED.value

            elif status == self.get_language_value(CONTAINED_WORD):
                node.store_status = StoreStatusEnum.EXPIRED.value

            merge_obs_nodes.append(node)
            self.logger.info(f"after_long_contra_repeat: {node.content} store_status={node.store_status} "
                             f"action_status={node.action_status}")

        # save context
        self.memory_manager.set_memories(MERGE_OBS_NODES, merge_obs_nodes)
