"""
Registry for different modules.
Init class according to the class name and verify the input parameters.
"""
import inspect


class Registry:
    def __init__(self, name):
        self.name = name
        self.module_dict = dict()

    def register_module(self, module, module_name=None):
        if module_name is None:
            module_name = module.__name__
        if module_name in self.module_dict:
            raise KeyError(f'{module_name} is already registered in {self.name}')
        self.module_dict[module_name] = module

    def get_module(self, module_name):
        assert module_name in self.module_dict, f'{module_name} not found in {self.name}'
        return self.module_dict[module_name]


def build_from_cfg(config, registry, default_args: dict = None, skip_param_check=False):

    if default_args is None:
        default_args = {}

    args = config.copy()
    method_type = args.pop('method')
    #params = args.get("parameters", {}) or default_args
    params = args
    if isinstance(method_type, str):
        obj_cls = registry.get_module(method_type)   
    else:
        raise TypeError(
            f'type must be a str or valid type, but got {type(method_type)}')

    allowed_params = list(inspect.signature(obj_cls.__init__).parameters.keys())
    print(allowed_params, params)
    if not skip_param_check:
        filter_params = {key: value for key, value in params.items() if key in allowed_params}
    else:
        filter_params = params
    # print(
    #     f"Registry {registry.name}, "
    #     f"allowed parameters {allowed_params}, filter parameters {filter_params}",
    #     flush=True
    # )
    print(filter_params)
    return obj_cls(**filter_params)


