from datetime import datetime
from typing import List

from memory_scope.utils.tool_functions import time_to_formatted_str, get_datetime_info_dict, prompt_to_msg
from memory_scope.constants.common_constants import (
    NEW_INSIGHT_NODES,
    DT,
    NOT_REFLECTED_MERGE_NODES,
    NEW_INSIGHT_KEYS
)
from memory_scope.enumeration.memory_status_enum import MemoryNodeStatus
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.constants.language_constants import NONE_WORD


class GetInsightWorker(MemoryBaseWorker):
    def new_insight_node(self, insight_key: str, insight_value: str) -> MemoryNode:
        created_dt = datetime.now()
        obs_dt = time_to_formatted_str(time=created_dt)
        meta_data = {k: str(v) for k, v in get_datetime_info_dict(created_dt).items()}
        content = self.prompt_handler.content_format.format(insight_key=insight_key, insight_value=insight_value)
        return MemoryNode(
            content=content,
            user_name=self.user_name,
            target_name=self.target_name,
            memory_type=MemoryTypeEnum.INSIGHT.value,
            meta_data=meta_data,
            status=MemoryNodeStatus.ACTIVE.value,
            obs_dt=obs_dt,
            obs_updated=True,
            insight_key=insight_key,
            insight_value=insight_value,
        )

    def reflect_new_insight_key(
        self, insight_key: str, not_reflected_merge_nodes: List[MemoryNode]
    ) -> MemoryNode | None:

        # 检索历史memory
        related_nodes = self.vector_store.similar_search(
            text=insight_key,
            size=self.es_insight_similar_top_k,
            exact_filters={
                "user_name": self.user_name,
                "target_name": self.target_name,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memory_type": [
                    MemoryTypeEnum.OBSERVATION.value,
                    MemoryTypeEnum.OBS_CUSTOMIZED.value,
                ],
            },
        )

        # 合并新增nodes
        related_nodes.extend(not_reflected_merge_nodes)

        # content去重
        related_node_dict = {n.memory_node.content: n for n in related_nodes}
        related_nodes = sorted(
            list(related_node_dict.values()), key=lambda x: x.memory_node.memory_id  # memory_id or use_id?
        )
        documents = [n.memory_node.content for n in related_nodes]

        # 重排所有记忆
        result = self.rank_model.call(query=insight_key, documents=documents)
        if not result:
            self.add_run_info(
                f"reflect insight_key={insight_key} call rerank client failed!"
            )
            return

        # 根据打分过滤
        for index, score in result.rank_scores.items():
            related_nodes[index].score_rank = score

        related_nodes_sorted = sorted(
            related_nodes, key=lambda x: x.score_rank, reverse=True
        )[: self.insight_obs_max_cnt]

        # prepare prompt
        user_query_list = [x.memory_node.content for x in related_nodes_sorted]
        get_insight_message = prompt_to_msg(
            system_prompt=self.prompt_handler.system_prompt,
            few_shot=self.prompt_handler.few_shot_prompt,
            user_query=self.prompt_handler.user_query_prompt.format(
                insight_key=insight_key, user_query="\n".join(user_query_list)
            )
        )

        self.logger.info(f"get_insight_message={get_insight_message}")

        # call LLM, 提取insight
        response = self.generation_model.call(
            messages=get_insight_message,
            model_name=self.get_insight_model,
            max_token=self.get_insight_max_token,
            temperature=self.get_insight_temperature,
            top_k=self.get_insight_top_k,
        )
        # return if empty
        if not response:
            self.add_run_info("reflect_upon_user_attr call llm failed!")
            return
        response_text = response.message.content.strip()
        if response_text in [self.get_language_value(NONE_WORD)]:
            return
        return self.new_insight_node(
            insight_key=insight_key, insight_value=response_text
        )

    def _run(self):
        new_insight_keys: List[MemoryNode] = self.get_context(NEW_INSIGHT_KEYS)
        if not new_insight_keys:
            self.add_run_info("new_insight_keys is empty! stop insight.")
            return

        not_reflected_merge_nodes: List[MemoryNode] = self.get_context(
            NOT_REFLECTED_MERGE_NODES
        )
        if not not_reflected_merge_nodes:
            self.add_run_info("not_reflected_merge_nodes is empty! stop get insight.")
            return

        # submit insight task
        for insight_key in new_insight_keys:
            self.submit_thread(
                self.reflect_new_insight_key,
                sleep_time=1,
                insight_key=insight_key,
                not_reflected_merge_nodes=not_reflected_merge_nodes,
            )

        # save output
        new_insight_nodes: List[MemoryNode] = []
        for result in self.join_threads():
            if result:
                new_insight_nodes.append(result)
                assert isinstance(result, MemoryNode)
                insight_key = result.insight_key
                insight_value = result.insight_value
                self.logger.info(
                    f"after_get_insight insight_key={insight_key} insight_value={insight_value}"
                )

        self.set_context(NEW_INSIGHT_NODES, new_insight_nodes)

        # set REFLECTED
        for node in not_reflected_merge_nodes:
            node.obs_reflected = True
