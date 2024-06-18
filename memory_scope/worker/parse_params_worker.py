import json

from config.bailian_memory_config import BailianMemoryConfig
from constants.common_constants import REQUEST, CONFIG
from request.memory import MemoryServiceRequestModel
from worker.memory.base_worker import BaseWorker


class ParseParamsWorker(BaseWorker):

    def _run(self):
        # 参数合并
        memory_config = {}

        # 更新环境变量
        memory_config.update(self.context_handler.env_configs)

        # 更新请求参数
        request: MemoryServiceRequestModel = self.context_handler.get_context(REQUEST)
        memory_config.update(request.model_dump(exclude=set("ext_info", )))

        # 更新ext_info
        if request.ext_info:
            memory_config.update(request.ext_info)

        # 存入上下文
        memory_config_model: BailianMemoryConfig = BailianMemoryConfig(**memory_config)
        self.context_handler.set_context(CONFIG, memory_config_model)

        # 打印
        self.logger.info(f"memory_config_model={json.dumps(memory_config_model.model_dump(), ensure_ascii=False)}")

        # 上游可能没有传这个参数，可能隐藏在memory_id做区分
        if request.user_profile:
            for user_attr in request.user_profile:
                user_attr.scene = request.scene
