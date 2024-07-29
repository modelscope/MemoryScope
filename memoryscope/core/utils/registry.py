"""
Registry for different modules.
Init class according to the class name and verify the input parameters.
"""
from typing import Dict, Any, List


class Registry(object):
    """
    A registry to manage and instantiate various modules by their names, ensuring the uniqueness of registered entries.
    It supports both individual and bulk registration of modules, as well as retrieval of modules by name.

    Attributes:
        name (str): The name of the registry.
        module_dict (Dict[str, Any]): A dictionary holding registered modules where keys are module names and values are
         the modules themselves.
    """

    def __init__(self, name: str):
        """
        Initializes the Registry with a given name.

        Args:
            name (str): The name to identify this registry.
        """
        self.name: str = name
        self.module_dict: Dict[str, Any] = {}

    def register(self, module_name: str = None, module: Any = None):
        """
        Registers module in the registry in a single call.

        Args:
            module_name (str): The name of module to be registered.
            module (List[Any] | Dict[str, Any]): The module to be registered.

        Raises:
            NotImplementedError: If the input is already registered.
        """
        assert module is not None
        if module_name is None:
            module_name = module.__name__

        if module_name in self.module_dict:
            raise KeyError(f'{module_name} is already registered in {self.name}')
        self.module_dict[module_name] = module

    def batch_register(self, modules: List[Any] | Dict[str, Any]):
        """
        Registers multiple modules in the registry in a single call. Accepts either a list of modules or a dictionary
            mapping names to modules.

        Args:
            modules (List[Any] | Dict[str, Any]): A list of modules or a dictionary mapping module names to the modules.

        Raises:
            NotImplementedError: If the input is neither a list nor a dictionary.
        """
        if isinstance(modules, list):
            module_name_dict = {m.__name__: m for m in modules}
        elif isinstance(modules, dict):
            module_name_dict = modules
        else:
            raise NotImplementedError("Input must be a list or a dictionary.")
        self.module_dict.update(module_name_dict)

    def __getitem__(self, module_name: str):
        """
        Retrieves a registered module by its name using index notation.

        Args:
            module_name (str): The name of the module to retrieve.

        Returns:
            A registered module corresponding to the given name.

        Raises:
            AssertionError: If the specified module is not found in the registry.
        """
        assert module_name in self.module_dict, f"{module_name} not found in {self.name}"
        return self.module_dict[module_name]
