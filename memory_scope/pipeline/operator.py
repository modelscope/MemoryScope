# -*- coding: utf-8 -*-
"""A common base class for Pipeline"""
from abc import ABC
from abc import abstractmethod


class Operator(ABC):
    """
    Abstract base class `Operator` defines a protocol for classes that
    implement callable behavior.
    The class is designed to be subclassed with an overridden `__call__`
    method that specifies the execution logic for the operator.
    """

    @abstractmethod
    def __call__(self) -> None:
        """Calling function"""
