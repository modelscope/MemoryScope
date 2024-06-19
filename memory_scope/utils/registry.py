"""
Registry for different modules.
Init class according to the class name and verify the input parameters.
"""
import inspect
from typing import Dict, Any, List


class Registry(object):
    def __init__(self, name: str):
        self.name: str = name
        self.module_dict: Dict[str, Any] = {}

    def register(self, module: Any, module_name: str = None):
        if module_name is None:
            module_name = module.__name__

        if module_name in self.module_dict:
            raise KeyError(f'{module_name} is already registered in {self.name}')
        self.module_dict[module_name] = module

    def batch_register(self, modules: List[Any]):
        module_name_dict = {m.__name__: m for m in modules}
        self.module_dict.update(module_name_dict)

    def __getitem__(self, module_name: str):
        assert module_name in self.module_dict, f'{module_name} not found in {self.name}'
        return self.module_dict[module_name]




