import time
from typing import List

from memoryscope.constants.common_constants import INSIGHT_NODES, NOT_UPDATED_NODES, NOT_REFLECTED_NODES
from memoryscope.constants.language_constants import COLON_WORD, NONE_WORD, REPEATED_WORD
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.utils.response_text_parser import ResponseTextParser
from memoryscope.core.utils.tool_functions import cosine_similarity
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.action_status_enum import ActionStatusEnum
from memoryscope.scheme.memory_node import MemoryNode


class UpdateInsightWorker(MemoryBaseWorker):
    """
    This class is responsible for updating insight value in a memory system. It filters insight nodes
    based on their association with observed nodes, utilizes a ranking model to prioritize them,
    generates refreshed insights via an LLM, and manages node statuses and content updates,
    incorporating features for concurrent execution and logging.
    """
    FILE_PATH: str = __file__

    def _parse_params(self, **kwargs):
        self.update_insight_threshold: float = kwargs.get("update_insight_threshold", 0.1)
        self.generation_model_kwargs: dict = kwargs.get("generation_model_kwargs", {})
        self.update_insight_max_count: int = kwargs.get("update_insight_max_count", 5)
        self.enable_ranker: bool = self.memoryscope_context.meta_data["enable_ranker"]

    def filter_obs_nodes(self,
                         insight_node: MemoryNode,
                         obs_nodes: List[MemoryNode]) -> (MemoryNode, List[MemoryNode], float):
        """
        Filters observed nodes based on their relevance to a given insight node using a ranking model.

        Args:
            insight_node (MemoryNode): The insight node used as the basis for filtering.
            obs_nodes (List[MemoryNode]): A list of observed nodes to be filtered.

        Returns:
            tuple: A tuple containing:
                - The original insight node.
                - A list of filtered observed nodes that are relevant to the insight node.
                - The maximum relevance score among the filtered nodes.
        """
        max_score: float = 0
        filtered_nodes: List[MemoryNode] = []

        # Check if insight node key or value is empty and log a warning
        if not insight_node.key:
            self.logger.warning(f"insight_key={insight_node.key} is empty!")
            return insight_node, filtered_nodes, max_score

        if not obs_nodes:
            self.logger.warning("obs_nodes is empty!")
            return insight_node, filtered_nodes, max_score

        if not self.enable_ranker:
            if not insight_node.key_vector:
                key_vector: List[float] = self.embedding_model.call(text=insight_node.key).embedding_results
                if not key_vector:
                    self.logger.warning(f"embedding call {insight_node.key} failed!")
                    return insight_node, filtered_nodes, max_score

                insight_node.key_vector = key_vector

            score_recall_list = cosine_similarity(insight_node.key_vector, [x.vector for x in obs_nodes])
            assert len(score_recall_list) == len(obs_nodes), \
                f"size is not as excepted. {len(score_recall_list)} v.s. {len(obs_nodes)}"

            for score, node in zip(score_recall_list, obs_nodes):
                keep_flag = score >= self.update_insight_threshold
                if keep_flag:
                    filtered_nodes.append(node)
                    max_score = max(max_score, score)

                # Log information about each node's processing
                self.logger.info(f"insight_key={insight_node.key} content={node.content} "
                                 f"score={score} keep_flag={keep_flag}")

        else:
            # Call the ranking model to get scores for each observed node's content against the insight key
            documents = [x.content for x in obs_nodes]
            self.logger.debug(f"update.insight.rank key={insight_node.key} \n docs={'|'.join(documents)}")
            response = self.rank_model.call(query=insight_node.key, documents=documents)
            if not response.status:
                return insight_node, filtered_nodes, max_score

            # Iterate over the ranked scores to filter nodes
            for index, score in response.rank_scores.items():
                node = obs_nodes[index]
                # Determine if the node should be kept based on the threshold
                keep_flag = score >= self.update_insight_threshold
                if keep_flag:
                    filtered_nodes.append(node)
                    max_score = max(max_score, score)
                # Log information about each node's processing
                self.logger.info(f"insight_key={insight_node.key} content={node.content} "
                                 f"score={score} keep_flag={keep_flag}")

        # Warn if no nodes were filtered
        if not filtered_nodes:
            self.logger.warning(f"update_insight={insight_node.key} filtered_nodes is empty!")

        # Return the original insight node, the list of filtered nodes, and the highest score
        return insight_node, filtered_nodes, max_score

    def update_insight_node(self, insight_node: MemoryNode, insight_value: str):
        """
        Updates the MemoryNode with the new insight value.

        Args:
            insight_node (MemoryNode): The MemoryNode whose insight value needs to be updated.
            insight_value (str): The new insight value.

        Returns:
            MemoryNode: The updated MemoryNode with potentially revised insight value.
        """
        dt_handler = DatetimeHandler()
        key = self.prompt_handler.insight_string_format.format(name=self.target_name, key=insight_node.key)
        content = f"{key}{self.get_language_value(COLON_WORD)} {insight_value}"
        insight_node.content = content
        insight_node.value = insight_value
        insight_node.meta_data.update({k: str(v) for k, v in dt_handler.get_dt_info_dict(self.language).items()})
        insight_node.timestamp = dt_handler.timestamp
        insight_node.dt = dt_handler.datetime_format()
        if insight_node.action_status == ActionStatusEnum.NONE.value:
            insight_node.action_status = ActionStatusEnum.CONTENT_MODIFIED.value
        self.logger.info(f"after_update_{insight_node.key} value={insight_value}")
        return insight_node

    def update_insight(self, insight_node: MemoryNode, filtered_nodes: List[MemoryNode]) -> MemoryNode:
        """
        Updates the insight value of a given MemoryNode based on the context from a list of filtered MemoryNodes.

        Args:
            insight_node (MemoryNode): The MemoryNode whose insight value needs to be updated.
            filtered_nodes (List[MemoryNode]): A list of MemoryNodes used as context for updating the insight.

        Returns:
            MemoryNode: The updated MemoryNode with potentially revised insight value.
        """
        self.logger.info(f"Updating insight for key={insight_node.key}, old_value={insight_node.value}, "
                         f"with {len(filtered_nodes)} documents considered.")

        # Generate the prompt for updating insight
        user_query_list = [n.content for n in filtered_nodes]
        system_prompt = self.prompt_handler.update_insight_system.format(user_name=self.target_name)
        few_shot = self.prompt_handler.update_insight_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.update_insight_user_query.format(
            user_query="\n".join(user_query_list),
            insight_key=insight_node.key,
            insight_key_value=insight_node.key + self.get_language_value(COLON_WORD) + insight_node.value)
        # Construct the message for LLM interaction
        update_insight_message = self.prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot,
                                                    user_query=user_query)
        self.logger.info(f"Generated insight update message: {update_insight_message}")

        # Call the Language Model for insight update
        response = self.generation_model.call(messages=update_insight_message, **self.generation_model_kwargs)

        # Handle empty or invalid responses
        if not response.status or not response.message.content:
            return insight_node

        insight_value_list = ResponseTextParser(response.message.content, self.language,
                                                f"update_{insight_node.key}").parse_v1()
        if not insight_value_list:
            self.logger.warning(f"update_{insight_node.key} insight_value_list is empty!")
            return insight_node

        insight_value_list = insight_value_list[0]
        if not insight_value_list:
            self.logger.warning(f"update_{insight_node.key} insight_value_list is empty!")
            return insight_node

        insight_value = insight_value_list[0].lower()
        if not insight_value or insight_value in self.get_language_value([NONE_WORD, REPEATED_WORD]):
            self.logger.info(f"update_{insight_node.key} insight_value={insight_value} is invalid.")
            return insight_node

        if insight_node.value == insight_value:
            self.logger.info(f"value={insight_value} is same!")
            return insight_node

        self.update_insight_node(insight_node=insight_node, insight_value=insight_value)
        return insight_node

    def _run(self):
        """
        Executes the main routine of the UpdateInsightWorker. This involves filtering and updating insight nodes
        based on their association with observed nodes. It processes nodes in batches, selects the top nodes
        according to a scoring mechanism, and then initiates tasks to update these insights using an LLM. Finally,
        it updates the status of processed nodes and gathers the results from all threads.

        Steps include:
        1. Get lists of insight node.
        2. Get not updated, and not reflected observation nodes from memory.
        3. Filter and process active insight nodes with respective not updated observation nodes.
        4. Sort processed results by score and select the top N.
        5. Submit tasks to update insight value for the selected nodes.
        6. Gather the results of all update tasks.
        7. Mark processed nodes as updated in memory.
        """
        insight_nodes: List[MemoryNode] = self.memory_manager.get_memories(INSIGHT_NODES)
        not_updated_nodes: List[MemoryNode] = self.memory_manager.get_memories(NOT_UPDATED_NODES)
        not_reflected_nodes: List[MemoryNode] = self.memory_manager.get_memories(keys=[NOT_REFLECTED_NODES,
                                                                                       NOT_UPDATED_NODES])

        if not insight_nodes:
            self.logger.warning("insight_nodes is empty, stopping processing.")
            return

        # Process active insight nodes with corresponding not updated nodes
        for node in insight_nodes:
            if self.enable_parallel:
                time.sleep(1)
            if node.action_status == ActionStatusEnum.NEW.value:
                self.submit_thread_task(fn=self.filter_obs_nodes,
                                        insight_node=node,
                                        obs_nodes=not_reflected_nodes)
            else:
                self.submit_thread_task(fn=self.filter_obs_nodes,
                                        insight_node=node,
                                        obs_nodes=not_updated_nodes)

        # select top n
        result_list = []
        for result in self.gather_thread_result():
            insight_node, filtered_nodes, max_score = result
            if not filtered_nodes:
                continue
            result_list.append(result)
        result_sorted = sorted(result_list, key=lambda x: x[2], reverse=True)[: self.update_insight_max_count]

        # Submit tasks to update insights for the top nodes
        for insight_node, filtered_nodes, _ in result_sorted:
            if self.enable_parallel:
                time.sleep(1)
            self.submit_thread_task(fn=self.update_insight,
                                    insight_node=insight_node,
                                    filtered_nodes=filtered_nodes)

        # Gather the final results from all update tasks
        for _ in self.gather_thread_result():
            pass

        # delete empty nodes
        empty_nodes = [n for n in insight_nodes if not n.content.strip()]
        self.memory_manager.delete_memories(empty_nodes)

        for node in not_updated_nodes:
            node.obs_updated = 1
            node.action_status = ActionStatusEnum.MODIFIED
