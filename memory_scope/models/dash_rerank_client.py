from typing import List

import dashscope

from common.dash_client import DashClient
from constants.common_constants import DASH_ENV_URL_DICT, DASH_API_URL_DICT
from enumeration.dash_api_enum import DashApiEnum


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
