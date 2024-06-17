from enumeration.dash_api_enum import DashApiEnum
from enumeration.env_type import EnvType

APP_ENV = "APP_ENV"

PIPELINE = "pipeline"

WORKER = "worker"

MEMORY = "memory"

DEFAULT_SYSTEM_PROMPT = "default_system_prompt"

RELATED_MEMORIES = "related_memories"

MODIFIED_MEMORIES = "modified_memories"

RESPONSE_EXT_INFO = "response_ext_info"

REQUEST = "request"

CONFIG = "config"

PROMPT_CONFIG = "prompt_config"

MESSAGES = "messages"

EXTRACT_TIME_DICT = "extract_time_dict"

NEW_OBS_NODES = "new_obs_nodes"

NEW_OBS_WITH_TIME_NODES = "new_obs_with_time_nodes"

INSIGHT_NODES = "insight_nodes"

MERGE_OBS_NODES = "merge_obs_nodes"

NEW_INSIGHT_NODES = "new_insight_nodes"

TODAY_OBS_NODES = "today_obs_nodes"

ALL_NODES = "all_nodes"

ALL_MEMORIES = "all_memories"

SIMILAR_OBS_NODES = "similar_obs_nodes"

KEYWORD_OBS_NODES = "keyword_obs_nodes"

NOT_REFLECTED_OBS_NODES = "not_reflected_obs_nodes"

NOT_REFLECTED_MERGE_NODES = "not_reflected_merge_nodes"

NEW_INSIGHT_KEYS = "new_insight_keys"

INSIGHT_KEY = "insight_key"

INSIGHT_VALUE = "insight_value"

DT = "dt"

MSG_TIME = "msg_time"

NEW = "new"

TIME_INFER = "time_infer"

KEY_WORD = "key_word"

REFLECTED = "reflected"

NEW_USER_PROFILE = "new_user_profile"

RECALL_TYPE = "recall_type"

ALL_ONLINE_NODES = "all_online_nodes"

MAX_WORKERS = "max_workers"

TIME_MATCHED = "time_matched"

QUERY_KEYWORDS = "query_keywords"

DASH_ENV_URL_DICT = {
    EnvType.DAILY: "https://dashscope.aliyuncs.com",
    # EnvType.PRE: "https://dashscope.aliyuncs.com",
    EnvType.PRE: "http://nlb-a3gi6od2xpdx16ezde.cn-beijing.nlb.aliyuncs.com",
    EnvType.PROD: "http://ep-2zei3b9a7e2e447bd259.epsrv-2zexnj17q1p8mtjwe3dx.cn-beijing.privatelink.aliyuncs.com",
}

DASH_API_URL_DICT = {
    DashApiEnum.GENERATION: "/api/v1/services/aigc/text-generation/generation",
    DashApiEnum.EMBEDDING: "/api/v1/services/embeddings/text-embedding/text-embedding",
    DashApiEnum.RERANK: "/api/v1/services/rerank/text-rerank/text-rerank",
}

ES_ENV_URL_DICT = {
    EnvType.DAILY: "http://es-cn-lr53pmrna0002pffb.public.elasticsearch.aliyuncs.com:9200",
    EnvType.PRE: "http://ep-bp1i04ae830e377a26a4.epsrv-bp15vzbd1o3umr1girls.cn-hangzhou.privatelink.aliyuncs.com:9200",
    EnvType.PROD: "http://ep-2zeibdbbe2904414e741.epsrv-2zet33kwqg8bphgmm36f.cn-beijing.privatelink.aliyuncs.com:9200",
}

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

DATATIME_WORD_LIST = ["天", "周", "月", "年", "星期", "点", "分钟", "小时", "秒", "上午", "下午", "早上", "早晨",
                      "晚上", "中午", "日", "夜", "清晨", "傍晚", "凌晨", "岁"]

TIME_FORMAT_V1 = "{year}年{month}月{day}日{weekday}{hour}点"

DATATIME_KEY_MAP = {
    "年": "year",
    "月": "month",
    "日": "day",
    "周": "week",
    "星期几": "weekday",
}
