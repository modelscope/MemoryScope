from typing import Dict, List

from constants.common_constants import RELATED_MEMORIES, EXTRACT_TIME_DICT, ALL_ONLINE_NODES, \
    TIME_MATCHED
from model.memory.memory_wrap_node import MemoryWrapNode
from worker.memory.memory_base_worker import MemoryBaseWorker


class FuseRerankWorker(MemoryBaseWorker):
    def __init__(self, fuse_time_ratio, fuse_score_threshold, fuse_ratio_dict, *args, **kwargs):
        super(FuseRerankWorker, self).__init__(*args, **kwargs)
        self.fuse_score_threshold = fuse_score_threshold
        self.fuse_ratio_dict = fuse_ratio_dict
        # self.default_system_prompt = default_system_prompt
        self.fuse_time_ratio = fuse_time_ratio

    @property
    def output_max_count(self):
        return self.request.user.output_max_count

    @staticmethod
    def format_time_infer(time_infer: str, extract_time_dict: Dict[str, str], meta_data: Dict[str, str]):
        if time_infer:
            return time_infer

        time_infer = ""
        if "year" in extract_time_dict:
            value = meta_data.get("msg_year")
            if value:
                time_infer += f"{value}年"
            elif value == "-1":
                time_infer += f"每年"

        if "month" in extract_time_dict:
            value = meta_data.get("msg_month")
            if value:
                time_infer += f"{value}月"
            elif value == "-1":
                time_infer += f"每月"

        if "day" in extract_time_dict:
            value = meta_data.get("msg_day")
            if value:
                time_infer += f"{value}日"
            elif value == "-1":
                time_infer += f"每日"

        if "weekday" in extract_time_dict:
            value = meta_data.get("msg_weekday")
            if value:
                time_infer += value

        return time_infer

    def _run(self):
        # 解析时间meta信息
        extract_time_dict: Dict[str, str] = self.get_context(EXTRACT_TIME_DICT)
        all_online_nodes: List[MemoryWrapNode] = self.get_context(ALL_ONLINE_NODES)

        if not all_online_nodes:
            self.add_run_info("all_online_nodes is empty, stop")
            return

        filtered_nodes = []
        for node in all_online_nodes:
            if node.score_rank < self.fuse_score_threshold:
                continue

            # 根据类型给ratio
            type_ratio: float = self.fuse_ratio_dict.get(node.memory_node.memoryType, 0.1)

            # 时间系数，完全匹配才行
            fuse_time_ratio: float = 1.0
            match_event_flag = False
            match_msg_flag = False
            if extract_time_dict:
                match_event_flag = True
                for k, v in extract_time_dict.items():
                    event_value = node.memory_node.metaData.get(f"event_{k}", "")
                    if event_value in ["-1", v]:
                        continue
                    else:
                        match_event_flag = False
                        break

                match_msg_flag = True
                for k, v in extract_time_dict.items():
                    msg_value = node.memory_node.metaData.get(f"msg_{k}", "")
                    if msg_value == v:
                        continue
                    else:
                        match_msg_flag = False
                        break

                if match_event_flag or match_msg_flag:
                    fuse_time_ratio = self.fuse_time_ratio
                    node.memory_node.metaData[TIME_MATCHED] = "1"

            node.score_rerank = node.score_rank * type_ratio * fuse_time_ratio
            self.logger.info(f"content={node.memory_node.content} f_event={int(match_event_flag)} "
                             f"f_msg={int(match_msg_flag)} score_rerank={node.score_rerank}")
            filtered_nodes.append(node)

        # get output & save context
        filtered_nodes = sorted(filtered_nodes, key=lambda x: x.score_rerank, reverse=True)
        filtered_nodes = filtered_nodes[: self.output_max_count]
        related_memories: List[str] = []
        for node in filtered_nodes:
            content = node.memory_node.content

            # 如果命中时间逻辑
            if node.memory_node.metaData.get(TIME_MATCHED, "") == "1":
                # time_infer = node.memory_node.metaData.get(TIME_INFER)
                # if not time_infer:
                #     time_infer = self.format_time_infer(time_infer=time_infer,
                #                                         extract_time_dict=extract_time_dict,
                #                                         meta_data=node.memory_node.metaData)
                time_infer = self.format_time_infer(time_infer="",
                                                    extract_time_dict=extract_time_dict,
                                                    meta_data=node.memory_node.metaData)
                content = f"{time_infer}: {content}"
            related_memories.append(content)

        self.set_context(RELATED_MEMORIES, related_memories)
        # self.set_context(DEFAULT_SYSTEM_PROMPT, self.default_system_prompt)
