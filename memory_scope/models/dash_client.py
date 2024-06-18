import json
import time
from http import HTTPStatus

import requests

from utils.logger import Logger
from utils.timer import Timer
from enumeration.env_type import EnvType


class DashClient(object):

    def __init__(self,
                 request_id: str,
                 dash_scope_uid: str,
                 authorization: str,
                 workspace: str,
                 model_name: str,
                 env_type: EnvType | str = EnvType.DAILY,
                 timeout: int = None,
                 max_retry_count: int = 2,
                 retry_sleep_time: float = 1.0,
                 **kwargs):

        self.model_name: str = model_name
        self.env_type: EnvType = EnvType(env_type)
        self.timeout: int = timeout
        self.max_retry_count: int = max_retry_count
        self.retry_sleep_time: float = retry_sleep_time
        self.kwargs: dict = kwargs

        # 20240506 update by 泉雨
        # if authorization:
        #     workspace = ""
        #     dash_scope_uid = ""

        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': authorization,
            'X-Request-Id': request_id,
            'X-DashScope-Uid': dash_scope_uid,
            'X-DashScope-WorkSpace': workspace,
        }

        self.url: str = ""
        self.data = {}

        self.logger = Logger.get_logger()

    def before_call(self, model_name: str = None, **kwargs):
        pass

    def after_call(self, response_obj, **kwargs):
        pass

    def call_once(self, model_name: str = None, retry_cnt: int = 0, **kwargs):
        if model_name is None:
            model_name = self.model_name

        self.before_call(model_name=model_name, **kwargs)

        with Timer(self.__class__.__name__, log_time=False) as t:
            self.logger.debug(f"url={self.url} header={self.headers} data={self.data} timeout={self.timeout}")
            response = requests.post(url=self.url,
                                     headers=self.headers,
                                     data=json.dumps(self.data),
                                     timeout=self.timeout)

        if response.status_code == HTTPStatus.OK:
            response_obj = json.loads(response.text)
            self.logger.info(f"{self.__class__.__name__} env={self.env_type.value} {t.get_cost_info()}, "
                             f"call model={model_name} success! retry_cnt={retry_cnt}",
                             stacklevel=3)
            return self.after_call(response_obj, **kwargs), True

        else:
            self.logger.warning(f"{self.__class__.__name__} env={self.env_type.value} {t.get_cost_info()}, "
                                f"call model={model_name} failed! retry_cnt={retry_cnt} details={response.text}",
                                stacklevel=3)
            return None, False

    def call(self, model_name: str = None, **kwargs):
        for i in range(self.max_retry_count):
            result, flag = self.call_once(model_name=model_name, retry_cnt=i, **kwargs)
            if flag:
                return result
            else:
                time.sleep(self.retry_sleep_time)

        return None


class LLIClient(object):

    def __init__(self,
                 model_name: str,
                 timeout: int = None,
                 max_retry_count: int = 2,
                 retry_sleep_time: float = 1.0,
                 **kwargs):

        self.model_name: str = model_name
        self.timeout: int = timeout
        self.max_retry_count: int = max_retry_count
        self.retry_sleep_time: float = retry_sleep_time
        self.kwargs: dict = kwargs

        self.data = {}
        self.logger = Logger.get_logger()
    

    def before_call(self, **kwargs):
        pass

    def after_call(self, **kwargs):
        pass

    def call_once(self, **kwargs):
        pass

    def call(self, **kwargs):
        pass
    
