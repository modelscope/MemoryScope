from abc import ABCMeta, abstractmethod
from typing import Literal

OPERATION_TYPE = Literal["frontend", "backend"]


class BaseOperation(metaclass=ABCMeta):
    operation_type: OPERATION_TYPE = "frontend"

    @abstractmethod
    def run_operation(self):
        raise NotImplementedError

    def run_operation_backend(self):
        pass
