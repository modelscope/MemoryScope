from typing import List, Dict

import dashscope

from models.dash_client import DashClient, LLIClient
from constants.common_constants import DASH_ENV_URL_DICT, DASH_API_URL_DICT
from enumeration.dash_api_enum import DashApiEnum

import time
from typing import List, Dict
from utils.timer import Timer
from models import LLM
from utils.registry import build_from_cfg
from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.base.llms.types import (
    ChatResponse,
    CompletionResponse,
)


class DashGenerateClient(DashClient):
    """
    url: https://help.aliyun.com/document_detail/2712576.html
    """

    def __init__(self, model_name: str = dashscope.Generation.Models.qwen_max, **kwargs):
        super(DashGenerateClient, self).__init__(model_name=model_name, **kwargs)
        self.url = DASH_ENV_URL_DICT.get(self.env_type) + DASH_API_URL_DICT.get(DashApiEnum.GENERATION)

    def before_call(self, model_name: str = None, **kwargs):
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Dict[str, str]] = kwargs.pop("messages", [])

        input_text = {}
        if prompt:
            input_text["prompt"] = prompt
        elif messages:
            input_text["messages"] = messages
        else:
            raise RuntimeError("prompt and messages is both empty!")

        self.data = {
            "model": model_name,
            "input": input_text,
            "parameters": {**kwargs, **self.kwargs},
        }

    def after_call(self, response_obj, **kwargs):
        self.logger.debug(f"response_obj={response_obj}")
        output = response_obj["output"]
        if "text" in output:
            return output["text"]
        elif "choices" in output:
            return output["choices"][0]["message"]["content"]
        else:
            raise NotImplementedError


class LLILLM(LLIClient):

    def __init__(self, method, model_name: str, **kwargs):
        super(LLILLM, self).__init__(model_name, **kwargs)
        self.config = {
                       "method": method,
                       "model_name": model_name,
                       **kwargs}
        self.llm = build_from_cfg(self.config, LLM)


    def before_call(self, model_name: str = None, **kwargs):
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Dict[str, str]] = kwargs.pop("messages", [])

        if prompt:
            input_text = prompt
            input_type = 'prompt'
            llama_input = input_text
        elif messages:
            input_text = messages
            input_type = 'messages'
            llama_input = [ChatMessage(
                role=x['role'], content=x['content']
            ) for x in input_text]
        else:
            raise RuntimeError("prompt and messages is both empty!")

        self.data = {
            input_type: llama_input,
        }

    def after_call(self, response_obj, **kwargs):
        self.logger.debug(f"response_obj={response_obj}")
        if isinstance(response_obj, CompletionResponse):
            return response_obj.text
        elif isinstance(response_obj, ChatResponse):
            return response_obj.message.content
        else:
            raise NotImplementedError
        
    
    def call_once(self, model_name: str = None, retry_cnt: int = 0, **kwargs):
        if model_name is None:
            model_name = self.model_name

        self.before_call(model_name=model_name, **kwargs)

        with Timer(self.__class__.__name__, log_time=False) as t:
            self.logger.debug(f"data={self.data} timeout={self.timeout}")
            if True:
          # try:
                if 'prompt' in self.data:
                    results = self.llm.complete(**self.data)
                else:
                    results = self.llm.chat(**self.data)    
                results = self.after_call(results)
                return results, True
          #  except:
          #      return None, False
        

    def call(self, model_name: str = None, **kwargs):
        for i in range(self.max_retry_count):
            result, flag = self.call_once(model_name=model_name, retry_cnt=i, **kwargs)
            print("dashscope llm results:",result)
            if flag:
                return result
            else:
                time.sleep(self.retry_sleep_time)
        return None