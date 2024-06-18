import datetime
import os
import time
from typing import List, Dict

from memory_scope.utils.logger import Logger
from memory_scope.constants.common_constants import NEW_USER_PROFILE, MODIFIED_MEMORIES, RELATED_MEMORIES
from memory_scope.enumeration.memory_method_enum import MemoryMethodEnum
from memory_scope.node.memory_node import MemoryNode
from memory_scope.node.user_attribute import UserAttribute
from memory_scope.pipeline.memory import MemoryServiceRequestModel
from memory_scope.pipeline.memory_service import MemoryService

"""
任务：随机生成一个用户的画像，随机种子0，并根据用户的画像虚拟一段用户和AI的对话。
步骤：
1. 帮忙生成一个用户的画像：包括用户的姓名，性别，工作地点，朋友关系，饮食偏好，游戏偏好，运动偏好等等属性。
2. 根据用户的画像虚拟一段用户和AI（比如通义千问）的对话，可以是用户的生活轨迹，生活事件，工作事件，也可以是用户的一些看法等等。要求对话中需要包含用户画像信息，并可以通过对话反推出部分用户画像。
用户画像格式，最少10个用户画像：
<用户画像，例如性别>: <属性值，例如男性>
用户对话格式，最少20轮对话：
<轮次> <用户>：<用户问题>
<轮次> <AI>：<回答>
    """

os.environ["APP_ENV"] = "daily"
os.environ["memory_retrieve_pipeline"] = """
parse_params,es.load_profile,[retrieve.extract_time|es.es_similar|es.es_keyword],retrieve.semantic_rank,retrieve.fuse_rerank
""".strip()
os.environ["memory_summary_short_pipeline"] = """
parse_params,summary_short.info_filter,[es.es_today_obs|summary_short.get_observation|summary_short.get_observation_with_time],summary_short.contra_repeat,memory_store
""".strip()
os.environ["memory_summary_long_pipeline"] = """
parse_params,[es.load_profile|es.es_new_obs|es.es_insight],[summary_long.update_insight|summary_long.get_reflection,summary_long.get_insight|summary_long.update_profile],summary_long.summary_collect,memory_store
""".strip()

os.environ["memory_summary_long_reflect_obs_cnt_threshold"] = "5"
os.environ["memory_summary_long_max_workers"] = "5"

# attrs = {
#     "性别": ["男性或者女性", 1],
#     "工作地点": ["工作所在城市", 1],
#     "朋友关系": ["和谁是什么朋友", 0],
#     "饮食偏好": ["喜欢吃什么菜", 0],
#     "游戏偏好": ["喜欢玩什么游戏", 0],
#     "运动偏好": ["喜欢什么运动", 0],
#     "音乐偏好": ["喜欢听什么音乐", 0],
#     "电影类型偏好": ["喜欢看什么类型的电影", 0],
#     "阅读偏好": ["喜欢看什么书", 0],
#     "购物习惯": ["喜欢买什么东西", 0],
# }
#
# os.environ["memory_summary_extra_user_attrs_TONGYI_MAIN_CHAT"] = ",".join(
#     [f"{k}:{v[0]}:{v[1]}" for k, v in attrs.items()])

memory_id: str = "jinli_0607_v26"
workspace_id: str = ""
api_key: str = "sk-AdrklI1sWM"
scene: str = "TONGYI_MAIN_CHAT"
algo_version: str = ""
output_max_count: int = 3
"""
'工作地点:工作所在城市:1',
'所在地:当前所在地点:1',
'饮食偏好:喜欢吃什么菜:0',
'游戏偏好:喜欢玩什么游戏:0',
'运动偏好:喜欢什么运动:0',
"""
user_profile: List[UserAttribute] = [
    UserAttribute(memory_key="运动偏好", value=["足球"], description="喜欢什么运动", is_unique=0),
    UserAttribute(memory_key="工作地点", description="工作所在城市", is_unique=1),
    UserAttribute(memory_key="所在地", description="当前所在地点", is_unique=1),
    UserAttribute(memory_key="饮食偏好", description="喜欢吃什么菜", is_unique=0),
    UserAttribute(memory_key="游戏偏好", description="喜欢玩什么游戏", is_unique=0),
    UserAttribute(memory_key="运动偏好", description="喜欢什么运动", is_unique=0),
]
ext_info: Dict[str, str] = {}
trace_id: str = "jinli_0530_req_id"
request_id: str = "jinli_0530_req_id"
account_id: str = "jinli"
app_id: str = "jinli_id"
uid: str = "1656375133437235"

messages1 = [
    {"role": "user", "content": "你知道北京哪里的海鲜最新鲜吗？", "time_created": "1717037394"},
    {"role": "user", "content": "有没有推荐的策略游戏？最近想找新的挑战。", "time_created": "1717037404"},
    {"role": "user", "content": "听说篮球运动对身体很好，是真的吗？", "time_created": "1717037414"},
    {"role": "user", "content": "最近在北京的工作压力太大，有什么放松的建议吗？", "time_created": "1717037424"},
    {"role": "user", "content": "说到朋友，我确实有几位很要好的朋友，我们经常一起出去吃饭。",
     "time_created": "1717037434"},
    {"role": "user", "content": "对了，最近想换工作，你觉得北京的哪个区工作机会更多？", "time_created": "1717037444"},
    {"role": "user", "content": "听你这么说，我感觉挺有信心的，谢了！", "time_created": "1717037454"},
    {"role": "user", "content": "我很喜欢尝试新的美食，有没有推荐的美食应用？", "time_created": "1717037464"},
    {"role": "user", "content": "我有时也喜欢自己在家做饭，你有没有好的海鲜菜谱推荐？", "time_created": "1717037474"},
    {"role": "user", "content": "听说打篮球可以长高，这是真的吗？", "time_created": "1717037484"},
    {"role": "user", "content": "昨天是我的生日！", "time_created": "1717037494"},
    {"role": "user", "content": "昨天和同学一起在我家开了party，庆祝了我的生日！", "time_created": "1717037494"},
    {"role": "user", "content": "我在北京阿里云园区工作", "time_created": "1717037504"},
    {"role": "user", "content": "我是阿里云百炼的工程师", "time_created": "1717037504"},
    {"role": "user", "content": "最后一个问题，你知道怎么才能维持广泛的社交关系吗？", "time_created": "1717037504"},

]
dt_n = datetime.datetime(year=2024, month=6, day=1, hour=12)
ts = int(dt_n.timestamp())
for i, msg in enumerate(messages1):
    msg["time_created"] = str(ts + i * 10)

messages2 = [
    # {"role": "user", "content": "今天我和客户团队的工程师张三讨论了技术方案，聊得很愉快",
    #  "time_created": "1717037394"},
    # {"role": "user", "content": "帮我记一下，我和他沟通约定3天后到杭州上门提供技术解决方案",
    #  "time_created": "1717037394"},
    {"role": "user", "content": "帮我记一下，我和客户团队的工程师张三沟通约定3天后到杭州上门提供技术解决方案",
     "time_created": "1717037394"},
]
dt_n = datetime.datetime(year=2024, month=6, day=3, hour=12)
ts = int(dt_n.timestamp())
for i, msg in enumerate(messages2):
    msg["time_created"] = str(ts + i * 10)

messages3 = [
    {"role": "user", "content": "我今天出差来深圳君悦酒店了，给张三发个邮件说一下事情", "time_created": "1717037394"},
    {"role": "user", "content": "我最近肠胃不好，吃不了辣", "time_created": "1717037394"},
    {"role": "user", "content": "最近肠胃养好了，换一些川菜吧", "time_created": "1717037394"},
]
dt_n = datetime.datetime(year=2024, month=6, day=6, hour=12)
ts = int(dt_n.timestamp())
for i, msg in enumerate(messages3):
    msg["time_created"] = str(ts + i * 10)

messages4 = [
    {"role": "user", "content": "附近有什么好吃的", "time_created": "1717037394"},
    {"role": "user", "content": "今天天气怎么样？", "time_created": "1717037394"},
]
dt_n = datetime.datetime(year=2024, month=6, day=6, hour=13)
ts = int(dt_n.timestamp())
for i, msg in enumerate(messages3):
    msg["time_created"] = str(ts + i * 10)


def summary_short(messages):
    request: MemoryServiceRequestModel = MemoryServiceRequestModel(
        messages=messages,
        memory_id=memory_id,
        workspace_id=workspace_id,
        api_key=api_key,
        scene=scene,
        algo_version=algo_version,
        output_max_count=output_max_count,
        user_profile=user_profile,
        ext_info=ext_info,
        trace_id=trace_id,
        tenant_id=trace_id,
        request_id=request_id,
        account_id=account_id,
        app_id=app_id,
        uid=uid,
    )

    logger = Logger.get_memory_logger()
    logger.set_trace_id(request.trace_id)
    memory_service = MemoryServiceBailian(request, method=MemoryMethodEnum.SUMMARY_SHORT)
    memory_service.run()

    modified_memories: List[MemoryNode] = memory_service.get_context(MODIFIED_MEMORIES)
    return modified_memories


def summary_long():
    request: MemoryServiceRequestModel = MemoryServiceRequestModel(
        messages=[],
        memory_id=memory_id,
        workspace_id=workspace_id,
        api_key=api_key,
        scene=scene,
        algo_version=algo_version,
        output_max_count=output_max_count,
        user_profile=user_profile,
        ext_info=ext_info,
        trace_id=trace_id,
        tenant_id=trace_id,
        request_id=request_id,
        account_id=account_id,
        app_id=app_id,
        uid=uid,
    )
    logger = Logger.get_memory_logger()
    logger.set_trace_id(request.trace_id)
    memory_service = MemoryServiceBailian(request, method=MemoryMethodEnum.SUMMARY_LONG)
    memory_service.run()

    user_profiles: List[UserAttribute] = memory_service.get_context(NEW_USER_PROFILE)
    modified_memories: List[MemoryNode] = memory_service.get_context(MODIFIED_MEMORIES)
    # ext_infos = memory_service.get_context(RESPONSE_EXT_INFO)
    # logger.info(f"user_profile=\n{json.dumps([x.model_dump() for x in user_profiles], ensure_ascii=False)}")
    # logger.info(f"modified_memories=\n{json.dumps([x.model_dump() for x in modified_memories], ensure_ascii=False)}")
    # logger.info(f"ext_info=\n{json.dumps(ext_infos, ensure_ascii=False)}")
    return user_profiles, modified_memories


def retrieve(messages):
    request: MemoryServiceRequestModel = MemoryServiceRequestModel(
        messages=messages,
        memory_id=memory_id,
        workspace_id=workspace_id,
        api_key=api_key,
        scene=scene,
        algo_version=algo_version,
        output_max_count=output_max_count,
        user_profile=user_profile,
        ext_info=ext_info,
        trace_id=trace_id,
        tenant_id=trace_id,
        request_id=request_id,
        account_id=account_id,
        app_id=app_id,
        uid=uid,
    )

    logger = Logger.get_memory_logger()
    logger.set_trace_id(request.trace_id)
    memory_service = MemoryServiceBailian(request, method=MemoryMethodEnum.RETRIEVE)
    memory_service.run()

    modified_memories: List[str] = memory_service.get_context(RELATED_MEMORIES)
    return modified_memories


if __name__ == "__main__":
    logger = Logger.get_memory_logger()

    summary1 = summary_short(messages1)
    logger.info(f"summary1={summary1}")

    summary2 = summary_short(messages2)
    logger.info(f"summary2={summary2}")

    for i, msg in enumerate(messages3):
        time.sleep(6)
        retrieve_res = retrieve([msg])
        logger.info(f"index={i} retrieve_res={retrieve_res}")

        summary_res = summary_short([msg])
        logger.info(f"index={i} summary_res={summary_res}")

    summary3 = summary_long()
    logger.info(f"summary3={summary3}")

    time.sleep(6)
    for i, msg in enumerate(messages4):
        retrieve_res = retrieve([msg])
        logger.info(f"index={i} retrieve_res={retrieve_res}")
