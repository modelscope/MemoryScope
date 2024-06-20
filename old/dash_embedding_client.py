from typing import List, Dict

import dashscope
import time 

from models import EMB
from models.dash_client import DashClient, LLIClient

from typing import List, Dict
from utils.registry import build_from_cfg
from utils.timer import Timer


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

class LLIEmbedding(LLIClient):

    def __init__(self, method, model_name, **kwargs):
        super(LLIEmbedding, self).__init__(model_name, **kwargs)
        self.config = {
                       "method": method,
                       "model_name": model_name,
                       **kwargs}
        self.embedder = build_from_cfg(self.config, EMB)

    def before_call(self, **kwargs):
        text: str | List[str] = kwargs.pop("text", "")

        if isinstance(text, str):
            text = [text]
        self.data = dict(texts=text)

    def after_call(self, emb: Dict[int, List[float]], **kwargs) -> Dict[int, List[float]] | List[float]:
        embedding_results = {}
        for idx, e in enumerate(emb):
            embedding_results[idx] = e

        if len(embedding_results) == 1:
            embedding_results = list(embedding_results.values())[0]
        return embedding_results


    def call_once(self, model_name: str = None, retry_cnt: int = 0, **kwargs):
        if model_name is None:
            model_name = self.model_name

        self.before_call(model_name=model_name, **kwargs)
        with Timer(self.__class__.__name__, log_time=False) as t:
            self.logger.debug(f"data={self.data} timeout={self.timeout}")
            try:
                results = self.embedder.get_text_embedding_batch(**self.data)  
                results = self.after_call(results)
                return results, True
            except Exception as e:
                self.logger.debug(f"Get Error in Embedding: {e}")
                return None, False
        

    def call(self, model_name: str = None, **kwargs):
        for i in range(self.max_retry_count):
            result, flag = self.call_once(model_name=model_name, retry_cnt=i, **kwargs)
            if flag:
                return result
            else:
                time.sleep(self.retry_sleep_time)
        return None