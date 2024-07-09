from typing import List, Dict

from memory_scope.constants.common_constants import NOT_UPDATED_NODES, MERGE_OBS_NODES
from memory_scope.constants.language_constants import NONE_WORD, INCLUDED_WORD, CONTRADICTORY_WORD
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.utils.tool_functions import prompt_to_msg


class LongContraRepeatWorker(MemoryBaseWorker):
    FILE_PATH: str = __file__

    def retrieve_similar_content(self, node: MemoryNode) -> (MemoryNode, List[MemoryNode]):
        filter_dict = {
            "user_name": self.user_name,
            "target_name": self.target_name,
            "status": MemoryNodeStatus.ACTIVE.value,
            "memory_type": [MemoryTypeEnum.OBSERVATION.value, MemoryTypeEnum.OBS_CUSTOMIZED.value]
        }
        retrieve_nodes = self.memory_store.retrieve_memories(query=node.content,
                                                             top_k=self.long_contra_repeat_top_k,
                                                             filter_dict=filter_dict)
        return node, [n for n in retrieve_nodes if n.score_similar >= self.long_contra_repeat_threshold]

    def _run(self):
        not_updated_nodes: List[MemoryNode] = self.get_memories(NOT_UPDATED_NODES)
        for node in not_updated_nodes:
            self.submit_thread_task(fn=self.retrieve_similar_content, node=node)

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

        # gene prompt
        user_query_list = []
        for i, n in enumerate(all_obs_nodes):
            user_query_list.append(f"{i + 1} {n.content}")
        system_prompt = self.prompt_handler.long_contra_repeat_system.format(num_obs=len(user_query_list),
                                                                             user_name=self.target_name)
        few_shot = self.prompt_handler.long_contra_repeat_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.long_contra_repeat_user_query.format(user_query="\n".join(user_query_list))

        long_contra_repeat_message = prompt_to_msg(system_prompt=system_prompt,
                                                   few_shot=few_shot,
                                                   user_query=user_query)
        self.logger.info(f"long_contra_repeat_message={long_contra_repeat_message}")

        # call llm
        response = self.generation_model.call(messages=long_contra_repeat_message, top_k=self.generation_model_top_k)

        # return if empty
        if not response or not response.message.content:
            return

        # parse text
        idx_obs_info_list = ResponseTextParser(response.message.content).parse_v1(self.__class__.__name__)
        if len(idx_obs_info_list) <= 0:
            self.logger.warning("idx_obs_info_list is empty!")
            return

        # add merged obs
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

            if status not in self.get_language_value([CONTRADICTORY_WORD, INCLUDED_WORD, NONE_WORD]):
                self.logger.warning(f"status={status} is invalid!")
                continue

            node: MemoryNode = all_obs_nodes[idx]
            if status == self.get_language_value(CONTRADICTORY_WORD):
                if not content:
                    node.status = MemoryNodeStatus.EXPIRED.value
                else:
                    node.content = content
                    node.status = MemoryNodeStatus.CONTENT_MODIFIED.value

            elif status == self.get_language_value(INCLUDED_WORD):
                node.status = MemoryNodeStatus.EXPIRED.value

            merge_obs_nodes.append(node)
            self.logger.info(f"after_long_contra_repeat: {node.content} {node.status}")

        # save context
        self.set_memories(MERGE_OBS_NODES, merge_obs_nodes)
