from typing import List

from constants.common_constants import SIMILAR_OBS_NODES, RECALL_TYPE
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_recall_type import MemoryRecallType
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class EsSimilarWorker(MemoryBaseWorker):

    def es_similar_obs(self) -> List[MemoryWrapNode]:
        query = self.messages[-1].content
        hits = self.es_client.similar_search(text=query,
                                             size=self.config.es_similar_top_k,
                                             exact_filters={
                                                 "memoryId": self.config.memory_id,
                                                 "status": MemoryNodeStatus.ACTIVE.value,
                                                 "scene": self.scene.lower(),
                                                 "memoryType": MemoryTypeEnum.OBSERVATION.value})

        # 初始化成MemoryWrapNode，并加入召回源的参数
        similar_obs_nodes: List[MemoryWrapNode] = []
        for hit in hits:
            node = MemoryWrapNode.init_from_es(hit)
            node.memory_node.metaData[RECALL_TYPE] = MemoryRecallType.SIMILAR.value
            similar_obs_nodes.append(node)
        return similar_obs_nodes

    def es_similar_insight(self) -> List[MemoryWrapNode]:
        query = self.messages[-1].content
        hits = self.es_client.similar_search(text=query,
                                             size=self.config.es_similar_top_k,
                                             exact_filters={
                                                 "memoryId": self.config.memory_id,
                                                 "status": MemoryNodeStatus.ACTIVE.value,
                                                 "scene": self.scene.lower(),
                                                 "memoryType": MemoryTypeEnum.INSIGHT.value})

        # 初始化成MemoryWrapNode，并加入召回源的参数
        similar_obs_nodes: List[MemoryWrapNode] = []
        for hit in hits:
            node = MemoryWrapNode.init_from_es(hit)
            node.memory_node.metaData[RECALL_TYPE] = MemoryRecallType.SIMILAR.value
            similar_obs_nodes.append(node)
        return similar_obs_nodes

    def es_similar_obs_custom(self) -> List[MemoryWrapNode]:
        query = self.messages[-1].content
        hits = self.es_client.similar_search(text=query,
                                             size=self.config.es_similar_top_k,
                                             exact_filters={
                                                 "memoryId": self.config.memory_id,
                                                 "status": MemoryNodeStatus.ACTIVE.value,
                                                 "scene": self.scene.lower(),
                                                 "memoryType": MemoryTypeEnum.OBS_CUSTOMIZED.value})

        # 初始化成MemoryWrapNode，并加入召回源的参数
        similar_obs_nodes: List[MemoryWrapNode] = []
        for hit in hits:
            node = MemoryWrapNode.init_from_es(hit)
            node.memory_node.metaData[RECALL_TYPE] = MemoryRecallType.SIMILAR.value
            similar_obs_nodes.append(node)
        return similar_obs_nodes

    def _run(self):
        for func in [self.es_similar_obs, self.es_similar_insight, self.es_similar_obs_custom]:
            self.submit_thread(func, sleep_time=0.01)

        similar_obs_nodes: List[MemoryWrapNode] = []
        for result in self.join_threads():
            similar_obs_nodes.extend(result)

        self.logger.info(f"similar_obs_nodes.size={len(similar_obs_nodes)}")
        for node in similar_obs_nodes:
            self.logger.info(f"node={node.memory_node.content} "
                             f"score_similar={node.score_similar} "
                             f"type={node.memory_node.memoryType}")
        self.set_context(SIMILAR_OBS_NODES, similar_obs_nodes)
