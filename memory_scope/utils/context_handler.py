import os
import threading
from typing import Dict, Any

from common.logger import Logger
from constants.common_constants import APP_ENV
from enumeration.env_type import EnvType


class ContextHandler(object):
    # 环境类型：日常 预发 开发
    _env_type: EnvType | None = None

    # 所有环境变量
    _env_params = os.environ

    # 环境变量解析 -> config
    _env_configs: Dict[str, str] | None = None

    def __init__(self, scene: str, method: str, prefix: str = "memory", algo_version: str = ""):
        self.scene: str = scene
        self.method: str = method
        self.prefix: str = prefix
        self.algo_version: str = algo_version

        # 上下文 所有worker共享
        self.context_dict: Dict[str, Any] = {}

        # 日志
        self.logger = Logger.get_logger()

        # 全局锁
        self.context_lock = threading.Lock()

        # algo_version: 上游参数 > 环境变量参数
        self._update_algo_version()

    def _update_algo_version(self):
        # 上游传参优先
        if self.algo_version:
            return

        p_key = f"{self.prefix}_{self.method}_algo_version"
        p_key_with_scene = f"{p_key}_{self.scene}"

        if p_key_with_scene in self._env_params:
            self.algo_version = self._env_params.get(p_key_with_scene)

        if p_key in self._env_params:
            self.algo_version = self._env_params.get(p_key_with_scene)

    @property
    def env_type(self):
        if self._env_type is None:
            env_type = self._env_params.get(APP_ENV)
            assert env_type, f"env_type={env_type} is empty!"
            self._env_type = EnvType(env_type.lower())

        return self._env_type

    @property
    def env_configs(self):
        if self._env_configs is not None:
            return self._env_configs

        prefix: str = f"{self.prefix}_{self.method}_"
        all_ket_set = set()
        for k, v in self._env_params.items():
            if not k.startswith(prefix):
                continue

            if not v:
                continue

            # {key}_{scene}_{algo_version}
            raw_k = k.removeprefix(prefix)
            if self.scene in raw_k:
                raw_k_split = [x.strip("_") for x in raw_k.split(self.scene) if x.strip("_")]
                if len(raw_k_split) == 1:
                    raw_k = raw_k_split[0]
                elif len(raw_k_split) == 2:
                    algo_version = raw_k_split[1]
                    if algo_version != self.algo_version:
                        continue

                    raw_k = raw_k_split[0]
                else:
                    self.logger.info(f"_update_env_configs encounter error! k={k} v={v}")
                    continue

            all_ket_set.add(raw_k)

        self._env_configs = {}
        for k in all_ket_set:
            v = self.get_param(k)
            if v:
                self._env_configs[k] = v
        self.logger.info(f"update env_configs={self._env_configs}")
        return self._env_configs

    def get_env_config(self, key: str, default=None) -> str:
        return self.env_configs.get(key, default)

    def get_param(self, key: str, default=None):
        p_key = f"{self.prefix}_{self.method}_{key}"
        p_key_with_scene = f"{p_key}_{self.scene}"
        # memory_summary_{key}_tongyi_algo_v1 > memory_summary_{key}_tongyi > memory_summary_{key}

        if p_key_with_scene in self._env_params:
            p_key = p_key_with_scene

        if self.algo_version:
            p_key_with_version = f"{p_key_with_scene}_{self.algo_version}"
            if p_key_with_version in self._env_params:
                p_key = p_key_with_version

        return self._env_params.get(p_key, default)

    def get_context(self, key: str, default=None):
        # 多线程环境下，如果是指针下修改，不安全
        return self.context_dict.get(key, default)

    def set_context(self, key: str, value: Any, is_multi_thread: bool = False):
        if is_multi_thread:
            # add lock to multi thread
            with self.context_lock:
                self.context_dict[key] = value
        else:
            self.context_dict[key] = value
