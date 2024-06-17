from typing import List

from constants.common_constants import KEY_WORD, KEYWORD_OBS_NODES, RECALL_TYPE, QUERY_KEYWORDS
from enumeration.memory_node_status import MemoryNodeStatus
from enumeration.memory_recall_type import MemoryRecallType
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory_wrap_node import MemoryWrapNode
from worker.bailian.memory_base_worker import MemoryBaseWorker


class EsKeywordWorker(MemoryBaseWorker):

    def _run(self):
        query = self.messages[-1].content
        # keywords = jieba.analyse.extract_tags(query, topK=3, withWeight=False, allowPOS=()) # 分解关键词
        # keywords = jieba.cut(query, cut_all=False)  # 使用精确模式分词

        # 查询相关关键词
        keywords = set()
        query_keywords = set()
        for key, values in self.config.key_word_relate_dict.items():
            if key in query:
                keywords.add(key)
                keywords.update(values)
                query_keywords.add(values[0])
        keywords = list(keywords)

        self.set_context(QUERY_KEYWORDS, query_keywords)

        # 任意一个匹配都算
        hits = self.es_client.exact_search_v2(size=self.config.es_keyword_top_k,
                                              term_filters={
                                                  "memoryId": self.config.memory_id,
                                                  "status": MemoryNodeStatus.ACTIVE.value,
                                                  "scene": self.scene.lower(),
                                                  "memoryType": [MemoryTypeEnum.OBSERVATION.value,
                                                                 MemoryTypeEnum.INSIGHT.value,
                                                                 MemoryTypeEnum.OBS_CUSTOMIZED.value],
                                              },
                                              match_filters={
                                                  f"metaData.{KEY_WORD}": keywords,
                                              })

        # 初始化成MemoryWrapNode，并加入召回源的参数
        keyword_obs_nodes: List[MemoryWrapNode] = []
        for hit in hits:
            node = MemoryWrapNode.init_from_es(hit)
            node.memory_node.metaData[RECALL_TYPE] = MemoryRecallType.KEYWORD.value
            keyword_obs_nodes.append(node)
        self.logger.info(f"keyword_obs_nodes size={len(keyword_obs_nodes)}")
        for node in keyword_obs_nodes:
            self.logger.info(f"node={node.memory_node.content} score_similar={node.score_similar}")
        self.set_context(KEYWORD_OBS_NODES, keyword_obs_nodes)
