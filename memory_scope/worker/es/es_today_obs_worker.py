from typing import List

from utils.tool_functions import time_to_formatted_str
from constants.common_constants import TODAY_OBS_NODES, DT
from enumeration.memory_status_enum import MemoryNodeStatus
from enumeration.memory_type_enum import MemoryTypeEnum
from scheme.memory_node import MemoryNode
from worker.memory_base_worker import MemoryBaseWorker


class EsTodayObsWorker(MemoryBaseWorker):
    def __init__(self, es_today_obs_top_k, *args, **kwargs):
        super(EsTodayObsWorker, self).__init__(*args, **kwargs)
        self.es_today_obs_top_k = es_today_obs_top_k

    def _run(self):
        if not self.messages:
            self.logger.warning("messages is empty!")
            return
        msg_time_created = self.messages[-1].time_created
        today_obs_nodes = self.vector_store.retrieve(
            size=self.es_today_obs_top_k,
            filter_dict={
                "memoryId": self.memory_id,
                "status": MemoryNodeStatus.ACTIVE.value,
                "memoryType": MemoryTypeEnum.OBSERVATION.value,
                f"metaData.{DT}": time_to_formatted_str(msg_time_created),
            },
        )

        self.logger.info(f"retrieve_today_obs.size={len(today_obs_nodes)}")
        self.set_context(TODAY_OBS_NODES, today_obs_nodes)
