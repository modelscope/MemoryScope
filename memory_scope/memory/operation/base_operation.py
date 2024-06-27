from abc import ABCMeta, abstractmethod
from typing import Literal

OPERATION_TYPE = Literal["frontend", "backend"]


class BaseOperation(metaclass=ABCMeta):
    operation_type: OPERATION_TYPE = "frontend"

    def __init__(self, name: str, description: str = "", **kwargs):
        self.name: str = name
        self.description: str = description

    def init_workflow(self):
        pass

    @abstractmethod
    def run_operation(self):
        raise NotImplementedError

    def run_operation_backend(self):
        pass

    def stop_operation_backend(self):
        pass
