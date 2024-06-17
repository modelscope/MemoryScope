from typing import List, Dict

import dashscope

from common.dash_client import DashClient
from constants.common_constants import DASH_ENV_URL_DICT, DASH_API_URL_DICT
from enumeration.dash_api_enum import DashApiEnum


class DashEmbeddingClient(DashClient):
    """
    url: https://help.aliyun.com/document_detail/2782232.html?spm=a2c4g.2782227.0.0.76195b1d9UeBAk#a6a39590fegqx
    """

    def __init__(self, model_name: str = dashscope.TextEmbedding.Models.text_embedding_v2, **kwargs):
        super(DashEmbeddingClient, self).__init__(model_name=model_name, **kwargs)
        self.url = DASH_ENV_URL_DICT.get(self.env_type) + DASH_API_URL_DICT.get(DashApiEnum.EMBEDDING)

    def before_call(self, model_name: str = None, **kwargs):
        text: str | List[str] = kwargs.pop("text", "")
        # text_type: query or document
        text_type: str = kwargs.pop("text_type", "query")

        if isinstance(text, str):
            text = [text]

        self.kwargs["text_type"] = text_type
        self.data = {
            "model": model_name,
            "input": {
                "texts": text,
            },
            "parameters": {**kwargs, **self.kwargs},
        }

    def after_call(self, response_obj, **kwargs) -> Dict[int, List[float]] | List[float]:
        embedding_results = {}
        for emb in response_obj["output"]["embeddings"]:
            embedding_results[emb["text_index"]] = emb["embedding"]

        if len(embedding_results) == 1:
            embedding_results = list(embedding_results.values())[0]
        return embedding_results
