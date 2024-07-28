import inspect
import time
from abc import abstractmethod, ABCMeta
from typing import Any

from memoryscope.core.utils.logger import Logger
from memoryscope.core.utils.registry import Registry
from memoryscope.core.utils.timer import Timer
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.scheme.model_response import ModelResponse, ModelResponseGen

MODEL_REGISTRY = Registry("models")


class BaseModel(metaclass=ABCMeta):
    m_type: ModelEnum | None = None

    def __init__(self,
                 model_name: str,
                 module_name: str,
                 timeout: int = None,
                 max_retries: int = 3,
                 retry_interval: float = 1.0,
                 kwargs_filter: bool = True,
                 raise_exception: bool = True,
                 **kwargs):

        self.model_name: str = model_name
        self.module_name: str = module_name
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.retry_interval: float = retry_interval
        self.kwargs_filter: bool = kwargs_filter
        self.raise_exception: bool = raise_exception
        self.kwargs: dict = kwargs

        self._model: Any = None
        self.logger = Logger.get_logger()

    @property
    def model(self):
        if self._model is None:
            if self.module_name not in MODEL_REGISTRY.module_dict:
                raise RuntimeError(f"method_type={self.module_name} is not supported!")
            obj_cls = MODEL_REGISTRY[self.module_name]

            if self.kwargs_filter:
                allowed_kwargs = list(inspect.signature(obj_cls.__init__).parameters.keys())
                kwargs = {key: value for key, value in self.kwargs.items() if key in allowed_kwargs}
            else:
                kwargs = self.kwargs
            self._model = obj_cls(**kwargs)

        return self._model

    @abstractmethod
    def before_call(self, model_response: ModelResponse, **kwargs):
        pass

    @abstractmethod
    def after_call(self, model_response: ModelResponse, **kwargs) -> ModelResponse | ModelResponseGen:
        pass

    @abstractmethod
    def _call(self, model_response: ModelResponse, stream: bool = False, **kwargs):
        pass

    def call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        with Timer(self.__class__.__name__, time_log_type="none") as t:
            model_response = ModelResponse(m_type=self.m_type)

            self.before_call(stream=stream, model_response=model_response, **kwargs)
            for i in range(self.max_retries):
                if self.raise_exception:
                    self._call(stream=stream, model_response=model_response, **kwargs)
                else:
                    try:
                        self._call(stream=stream, model_response=model_response, **kwargs)
                    except Exception as e:
                        model_response.status = False
                        model_response.details = e.args

                if isinstance(model_response, ModelResponse) and not model_response.status:
                    self.logger.warning(f"call model={self.model_name} failed! {t.cost_str} retry_cnt={i} "
                                        f"details={model_response.details}", stacklevel=2)
                    time.sleep(i * self.retry_interval)
                else:
                    return self.after_call(stream=stream, model_response=model_response, **kwargs)

    @abstractmethod
    async def _async_call(self, model_response: ModelResponse, **kwargs) -> ModelResponse:
        pass

    async def async_call(self, **kwargs) -> ModelResponse:
        with Timer(self.__class__.__name__, time_log_type="none") as t:
            model_response = ModelResponse(m_type=self.m_type)

            self.before_call(model_response=model_response, **kwargs)
            for i in range(self.max_retries):
                if self.raise_exception:
                    await self._async_call(model_response=model_response, **kwargs)
                else:
                    try:
                        await self._async_call(model_response=model_response, **kwargs)
                    except Exception as e:
                        model_response.status = False
                        model_response.details = e.args

                if not model_response.status:
                    self.logger.warning(f"async_call model={self.model_name} failed! {t.cost_str} retry_cnt={i} "
                                        f"details={model_response.details}", stacklevel=2)
                    time.sleep(i * self.retry_interval)
                else:
                    return self.after_call(model_response=model_response, **kwargs)
