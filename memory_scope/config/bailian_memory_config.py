from typing import Dict, List

import dashscope
from pydantic import Field, BaseModel

from enumeration.memory_type_enum import MemoryTypeEnum


class BailianMemoryConfig(BaseModel):
    # constant
    qwen_max: str = dashscope.Generation.Models.qwen_max
    qwen_plus: str = dashscope.Generation.Models.qwen_plus
    qwen_turbo: str = dashscope.Generation.Models.qwen_turbo
    qwen_long: str = "qwen-long"

    # 关键词映射
    key_word_relate_dict: Dict[str, List[str]] = {
        "天气": ["地点", "工作"],
    }

    # 用户额外画像
    extra_user_attrs: List[str] = [

    ]

    # 记忆的系统prompt
    default_system_prompt: str = "请判断下面的内容是否可以帮助更好的理解用户问题，如果有用处，请记住下面的内容，如果没有用处，请遗忘下面的内容："

    # es config
    es_index_name: str = Field("memory_index", description="es_index_name")
    es_user_name: str = Field("elastic", description="es_user_name")
    es_password: str = Field("Beilianmemory_", description="es_password")

    # retry count
    dash_generate_retry_cnt: int = Field(2, description="dash_generate retry_cnt")
    dash_embedding_retry_cnt: int = Field(5, description="dash_embedding retry_cnt")
    dash_rerank_retry_cnt: int = Field(5, description="dash_rerank retry_cnt")
    es_retry_cnt: int = Field(5, description="es retry_cnt")

    # other config
    seed: int = Field(0, description="global seed")

    # memory request model
    messages_pick_n: int = Field(1, description="summary:需要总结的msg个数(偶数);retrieve:传1+History（奇数）")
    memory_id: str = Field("", description="base memory id")
    workspace_id: str = Field("", description="workspace_id")
    api_key: str = Field("", description="api_key")
    output_max_count: int = Field(5, description="output_max_count")

    # base request model
    trace_id: str = Field("", description="trace_id")
    tenant_id: str = Field("", description="tenant_id")
    request_id: str = Field("", description="request_id")
    uid: str = Field("", description="uid")
    account_id: str = Field("", description="account_id")
    app_id: str = Field("", description="app_id")

    # top k
    es_insight_top_k: int = Field(128, description="es_insight_top_k")
    es_keyword_top_k: int = Field(10, description="es_keyword_top_k")
    es_new_obs_top_k: int = Field(256, description="es_new_obs_top_k")
    es_not_reflected_top_k: int = Field(256, description="es_not_reflected_top_k")
    es_similar_top_k: int = Field(128, description="es_similar_top_k")
    es_today_obs_top_k: int = Field(128, description="es_today_obs_top_k")
    es_insight_similar_top_k: int = Field(128, description="es_insight_similar_top_k")
    es_contra_repeat_similar_top_k: int = Field(1, description="es_contra_repeat_similar_top_k")

    # parse_time_model
    parse_time_model: str = Field("qwen_1_8_parse_time_service", description="parse_time_model")
    parse_time_max_token: int = Field(100, description="parse_time_max_token")
    parse_time_temperature: float = Field(0.6, description="parse_time_temperature")
    parse_time_top_k: int = Field(1, description="parse_time_top_k")

    # info_score_model
    info_filter_msg_max_size: int = Field(200, description="info_filter_msg_max_size")
    info_filter_model: str = Field(qwen_max, description="info_filter_model")
    info_filter_max_token: int = Field(200, description="info_filter_max_token")
    info_filter_temperature: float = Field(0.6, description="info_filter_temperature")
    info_filter_top_k: int = Field(1, description="info_filter_top_k")

    # summary_messages_model
    summary_messages_model: str = Field(qwen_max, description="summary_messages_model")
    summary_messages_max_token: int = Field(500, description="summary_messages_max_token")
    summary_messages_temperature: float = Field(0.6, description="summary_messages_temperature")
    summary_messages_top_k: int = Field(1, description="summary_messages_top_k")

    # summarize_messages_model
    merge_obs_model: str = Field(qwen_max, description="merge_obs_model")
    merge_obs_max_token: int = Field(500, description="merge_obs_max_token")
    merge_obs_temperature: float = Field(0.6, description="merge_obs_temperature")
    merge_obs_top_k: int = Field(1, description="merge_obs_top_k")

    # fuse params
    fuse_score_threshold: float = Field(0.1, description="fuse_score_threshold")
    fuse_ratio_dict: Dict[str, float] = Field({
        MemoryTypeEnum.CONVERSATION.value: 0.8,
        MemoryTypeEnum.OBSERVATION.value: 1.0,
        MemoryTypeEnum.OBS_CUSTOMIZED.value: 1.0,
        MemoryTypeEnum.INSIGHT.value: 1.5,
        MemoryTypeEnum.PROFILE.value: 1.5,
        MemoryTypeEnum.PROFILE_CUSTOMIZED.value: 1.5,
    }, description="fuse_multiplier_dict")
    fuse_time_ratio: float = Field(2.0, description="fuse_ratio_dict")

    # update profile
    update_profile_threshold: float = Field(0.1, description="update_profile_threshold")
    update_profile_model: str = Field(qwen_max, description="update_profile_model")
    update_profile_max_token: int = Field(500, description="update_profile_max_token")
    update_profile_temperature: float = Field(0.6, description="update_profile_temperature")
    update_profile_top_k: int = Field(1, description="update_profile_top_k")
    update_profile_max_thread: int = Field(10, description="update_profile_max_thread")

    # reflection
    reflect_obs_cnt_threshold: int = Field(40, description="reflect_obs_cnt_threshold")
    reflect_num_questions: int = Field(3, description="reflect_num_questions")
    reflect_obs_model: str = Field(qwen_max, description="reflect_obs_model")
    reflect_obs_max_token: int = Field(300, description="reflect_obs_max_token")
    reflect_obs_temperature: float = Field(0.6, description="reflect_obs_temperature")
    reflect_obs_top_k: int = Field(1, description="reflect_obs_top_k")

    # get insight
    insight_obs_max_cnt: int = Field(10, description="insight_obs_max_cnt")
    get_insight_model: str = Field(qwen_max, description="get_insight_model")
    get_insight_max_token: int = Field(500, description="get_insight_max_token")
    get_insight_temperature: float = Field(0.6, description="get_insight_temperature")
    get_insight_top_k: int = Field(1, description="get_insight_top_k")

    # update insight
    update_insight_threshold: float = Field(0.1, description="update_insight_threshold")
    update_insight_model: str = Field(qwen_max, description="update_insight_model")
    update_insight_max_token: int = Field(500, description="update_insight_max_token")
    update_insight_temperature: float = Field(0.6, description="update_insight_temperature")
    update_insight_top_k: int = Field(1, description="update_insight_top_k")
    update_insight_max_thread: int = Field(10, description="update_insight_max_thread")

    # long contra repeat
    long_contra_repeat_threshold: float = Field(0.6, description="long_contra_repeat_threshold")