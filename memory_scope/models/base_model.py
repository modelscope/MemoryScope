import inspect
import time
from abc import abstractmethod, ABCMeta

from enumeration.model_enum import ModelEnum
from . import MODEL_REGISTRY
from .response import ModelResponse, ModelResponseGen
from utils.logger import Logger
from utils.timer import Timer


class BaseModel(metaclass=ABCMeta):
    m_type: ModelEnum | None = None

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
                try:
                    model_response = self._call(stream=stream, **kwargs)
                except Exception as e:
                    model_response = ModelResponse(m_type=self.m_type, status=False, details=e.args)

                if isinstance(model_response, ModelResponse) and not model_response.status:
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
                try:
                    model_response = await self._async_call(**kwargs)
                except Exception as e:
                    model_response = ModelResponse(status=False, details=e.args)

                if not model_response.status:
                    self.logger.warning(f"async_call model={self.model_name} failed! cost={t.cost_str} retry_cnt={i} "
                                        f"details={model_response.details}", stacklevel=2)
                    time.sleep(i * self.retry_interval)
                else:
                    return self.after_call(model_response=model_response, **kwargs)
