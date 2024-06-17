from typing import List, Dict

import dashscope

from common.dash_client import DashClient
from constants.common_constants import DASH_ENV_URL_DICT, DASH_API_URL_DICT
from enumeration.dash_api_enum import DashApiEnum


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
