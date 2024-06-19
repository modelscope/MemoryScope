import asyncio
import inspect
import time
from abc import abstractmethod, ABCMeta

from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.response import ModelResponse, ModelResponseGen
from memory_scope.utils.logger import Logger
from memory_scope.utils.timer import Timer


class BaseModel(metaclass=ABCMeta):

    def __init__(self,
                 model_name: str,
                 method_type: str,
                 timeout: int = None,
                 max_retries: int = 3,
                 retry_interval: float = 1.0,
                 kwargs_filter: bool = True,
                 **kwargs):
        self.model_name: str = model_name
        self.method_type: str = method_type
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.retry_interval: float = retry_interval
        self.kwargs: dict = kwargs

        self.data = {}
        self.logger = Logger.get_logger()

        obj_cls = MODEL_REGISTRY.get(self.method_type)
        if not obj_cls:
            raise RuntimeError(f"method_type={self.method_type} is not supported!")

        if kwargs_filter:
            allowed_kwargs = list(inspect.signature(obj_cls.__init__).parameters.keys())
            kwargs = {key: value for key, value in kwargs.items() if key in allowed_kwargs}

        self.model = obj_cls(**kwargs)

    @abstractmethod
    def before_call(self, **kwargs) -> None:
        """prepare data before call
        :param kwargs:
        :return:
        """

    @abstractmethod
    def after_call(self, model_response: ModelResponse | ModelResponseGen,
                   **kwargs) -> ModelResponse | ModelResponseGen:
        """
        :param model_response:
        :param kwargs:
        :return:
        """

    @abstractmethod
    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        """
        :param kwargs:
        :return:
        """

    def call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        """
        :param stream: only llm needs stream
        :param kwargs:
        :return:
        """
        self.before_call(stream=stream, **kwargs)
        with Timer(self.__class__.__name__, log_time=False) as t:
            for i in range(self.max_retries):
                model_response = self._call(stream=stream, **kwargs)
                if not model_response.status and not stream:
                    self.logger.warning(f"call model={self.model_name} failed! cost={t.cost_str} retry_cnt={i} "
                                        f"details={model_response.details}", stacklevel=2)
                    time.sleep(i * self.retry_interval)
                else:
                    return self.after_call(stream=stream, model_response=model_response, **kwargs)

    @abstractmethod
    async def _async_call(self, **kwargs) -> ModelResponse:
        """
        :param kwargs:
        :return:
        """

    async def async_call(self, **kwargs) -> ModelResponse:
        """ 异步不需要stream
        :param kwargs:
        :return:
        """
        self.before_call(**kwargs)
        with Timer(self.__class__.__name__, log_time=False) as t:
            for i in range(self.max_retries):
                model_response = await self._async_call(**kwargs)
                if not model_response.status:
                    self.logger.warning(f"async_call model={self.model_name} failed! cost={t.cost_str} retry_cnt={i} "
                                        f"details={model_response.details}", stacklevel=2)
                    await asyncio.sleep(i * self.retry_interval)
                else:
                    return self.after_call(model_response, **kwargs)
