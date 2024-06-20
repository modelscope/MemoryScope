from typing import List

import dashscope

from models.dash_client import DashClient, LLIClient
from constants.common_constants import DASH_ENV_URL_DICT, DASH_API_URL_DICT
from enumeration.dash_api_enum import DashApiEnum


import time
from typing import List
from models import RERANKER
from utils.timer import Timer

from utils.registry import build_from_cfg
from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore # type: ignore


class DashReRankClient(DashClient):
    """
    url: https://help.aliyun.com/document_detail/2780059.html
    """

    def __init__(self, model_name: str = dashscope.TextReRank.Models.gte_rerank, **kwargs):
        super(DashReRankClient, self).__init__(model_name=model_name, **kwargs)
        self.url = DASH_ENV_URL_DICT.get(self.env_type) + DASH_API_URL_DICT.get(DashApiEnum.RERANK)

    def before_call(self, model_name: str = None, **kwargs):
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])
        top_n: int | None = kwargs.pop("top_n", None)
        return_documents: bool = kwargs.pop("return_documents", False)

        assert query and documents, f"query or documents is empty! query={query}, documents={len(documents)}"
        if top_n is None:
            top_n = len(documents)

        self.kwargs.update({
            "top_n": top_n,
            "return_documents": return_documents,
        })
        self.data = {
            "model": model_name,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {**kwargs, **self.kwargs},
        }

    def after_call(self, response_obj, **kwargs):
        return response_obj["output"]["results"]


class LLIReRank(LLIClient):
   
    def __init__(self, method, model_name, **kwargs):
        super(LLIReRank, self).__init__(model_name, **kwargs)

        self.config = {
                       "method": method,
                       "model_name": model_name,
                       **kwargs}
        self.reranker = build_from_cfg(self.config, RERANKER)


    def before_call(self, model_name: str = None, **kwargs):
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])
        top_n: int | None = kwargs.pop("top_n", None)
        return_documents: bool = kwargs.pop("return_documents", False)
        
        assert query and documents, f"query or documents is empty! query={query}, documents={len(documents)}"
        if top_n is None:
            top_n = len(documents)
        
        nodes = [NodeWithScore(Node(text=text, score=1.0)) for text in documents]
        self.reranker = self.reranker(top_n=top_n, 
                                   return_documents=return_documents)

        self.data = {
            "nodes": nodes,
            "query_str": query,
        }
        

    def after_call(self, nodes: List[NodeWithScore], **kwargs) -> List[dict]:
        results = []
        for node in nodes:
            results.append(dict(relevance_score=node.score,
                                document=node.node.text))
        return results


    def call_once(self, model_name: str = None, retry_cnt: int = 0, **kwargs):
        if model_name is None:
            model_name = self.model_name

        self.before_call(model_name=model_name, **kwargs)

        with Timer(self.__class__.__name__, log_time=False) as t:
            self.logger.debug(f"data={self.data} timeout={self.timeout}")
            try:
                results = self.reranker.postprocess_nodes(*self.data)    
                results = self.after_call(results)
                return results, True
            except:
                return None, False
        

    def call(self, model_name: str = None, **kwargs):
        for i in range(self.max_retry_count):
            result, flag = self.call_once(model_name=model_name, retry_cnt=i, **kwargs)
            if flag:
                return result
            else:
                time.sleep(self.retry_sleep_time)
        return None