from datetime import datetime
from typing import List

from common.tool_functions import time_to_formatted_str, get_datetime_info_dict
from constants.common_constants import NEW_INSIGHT_NODES, DT, NOT_REFLECTED_MERGE_NODES, NEW_INSIGHT_KEYS, INSIGHT_KEY, \
    INSIGHT_VALUE, REFLECTED
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory.memory_wrap_node import MemoryWrapNode
from worker.memory.memory_base_worker import MemoryBaseWorker


class GetInsightWorker(MemoryBaseWorker):
    def __init__(self, insight_obs_max_cnt, es_insight_similar_top_k, get_insight_model, get_insight_max_token, get_insight_temperature, get_insight_top_k, **kwargs):
        super(GetInsightWorker,self).__init__(*args,**kwargs)
        self.insight_obs_max_cnt = insight_obs_max_cnt
        self.get_insight_model = get_insight_model
        self.get_insight_max_token = get_insight_max_token
        self.get_insight_temperature = get_insight_temperature
        self.get_insight_top_k = get_insight_top_k
        self.es_insight_similar_top_k = es_insight_similar_top_k

    def new_insight_node(self, insight_key: str, insight_value: str) -> MemoryWrapNode:
        created_dt = datetime.now()
        dt = time_to_formatted_str(time=created_dt)

        # 组合meta_data
        meta_data = {
            DT: dt,
            INSIGHT_KEY: insight_key,
            INSIGHT_VALUE: insight_value,
        }
        meta_data.update({k: str(v) for k, v in get_datetime_info_dict(created_dt).items()})

        content = f"用户的{insight_key}：{insight_value}"
        return MemoryWrapNode.init_from_attrs(content=content,
                                              memoryId=self.memory_id,
                                              scene=self.scene,
                                              memoryType=MemoryTypeEnum.INSIGHT.value,
                                              content_modified=True,  # 新增的insight需要置为true
                                              metaData=meta_data,
                                              status=MemoryNodeStatus.ACTIVE.value,
                                              tenantId=self.tenant_id)

    def reflect_new_insight_key(self,
                                insight_key: str,
                                not_reflected_merge_nodes: List[MemoryWrapNode]) -> MemoryWrapNode | None:

        # 检索历史memory
        hits = self.es_client.similar_search(text=insight_key,
                                             size=self.es_insight_similar_top_k,
                                             exact_filters={
                                                 "memoryId": self.memory_id,
                                                 "status": MemoryNodeStatus.ACTIVE.value,
                                                 "scene": self.scene.lower(),
                                                 "memoryType": [MemoryTypeEnum.OBSERVATION.value,
                                                                MemoryTypeEnum.OBS_CUSTOMIZED.value],
                                             })

        # 转化成 MemoryNodeWrap 合并新增nodes
        related_nodes: List[MemoryWrapNode] = [MemoryWrapNode.init_from_es(x) for x in hits]
        related_nodes.extend(not_reflected_merge_nodes)

        # content去重
        related_node_dict = {n.memory_node.content: n for n in related_nodes}
        related_nodes = sorted(list(related_node_dict.values()), key=lambda x: x.memory_node.id)
        documents = [n.memory_node.content for n in related_nodes]

        # 重排所有记忆
        result = self.rerank_client.call(query=insight_key, documents=documents)
        if not result:
            self.add_run_info(f"reflect insight_key={insight_key} call rerank client failed!")
            return

        # 根据打分过滤
        for rank_node in result:
            index = rank_node["index"]
            score = rank_node["relevance_score"]
            related_nodes[index].score_rank = score
        related_nodes_sorted = sorted(related_nodes, key=lambda x: x.score_rank, reverse=True)[
                               :self.insight_obs_max_cnt]

        # 生成prompt
        user_query_list = [x.memory_node.content for x in related_nodes_sorted]
        get_insight_message = self.prompt_to_msg(
            system_prompt=self.prompt_config.get_insight_system,
            few_shot=self.prompt_config.get_insight_few_shot,
            user_query=self.prompt_config.get_insight_user_query.format(
                insight_key=insight_key, user_query="\n".join(user_query_list)))
        self.logger.info(f"get_insight_message={get_insight_message}")

        # call LLM, 提取insight
        response_text = self.gene_client.call(messages=get_insight_message,
                                              model_name=self.get_insight_model,
                                              max_token=self.get_insight_max_token,
                                              temperature=self.get_insight_temperature,
                                              top_k=self.get_insight_top_k)

        # return if empty
        if not response_text:
            self.add_run_info("reflect_upon_user_attr call llm failed!")
            return
        response_text = response_text.strip()
        if response_text in ["无"]:
            return
        return self.new_insight_node(insight_key=insight_key, insight_value=response_text)

    def _run(self):
        new_insight_keys: List[MemoryWrapNode] = self.get_context(NEW_INSIGHT_KEYS)
        if not new_insight_keys:
            self.add_run_info("new_insight_keys is empty! stop insight.")
            return

        not_reflected_merge_nodes: List[MemoryWrapNode] = self.get_context(NOT_REFLECTED_MERGE_NODES)
        if not not_reflected_merge_nodes:
            self.add_run_info("not_reflected_merge_nodes is empty! stop get insight.")
            return

        # submit insight task
        for insight_key in new_insight_keys:
            self.submit_thread(self.reflect_new_insight_key,
                               sleep_time=1,
                               insight_key=insight_key,
                               not_reflected_merge_nodes=not_reflected_merge_nodes)

        # save output
        new_insight_nodes: List[MemoryWrapNode] = []
        for result in self.join_threads():
            if result:
                new_insight_nodes.append(result)
                assert isinstance(result, MemoryWrapNode)
                insight_key = result.memory_node.metaData.get(INSIGHT_KEY, "")
                insight_value = result.memory_node.metaData.get(INSIGHT_VALUE, "")
                self.logger.info(f"after_get_insight insight_key={insight_key} insight_value={insight_value}")

        self.set_context(NEW_INSIGHT_NODES, new_insight_nodes)

        # set REFLECTED
        for node in not_reflected_merge_nodes:
            node.memory_node.metaData[REFLECTED] = "1"
