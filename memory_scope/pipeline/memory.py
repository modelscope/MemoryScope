from typing import List, Dict

from pydantic import Field

from model.message import Message
from model.user_attribute import UserAttribute
from request.base_model import RequestBaseModel


class MemoryServiceRequestModel(RequestBaseModel):
    messages: List[Message] = Field(...,
                                    description="summary: 多轮对话的list,默认按照时间正序，最后一条是最新的; retrieve: 最后一条是query")

    messages_pick_n: int = Field(1, description="summary：传需要总结的msg的个数;retrieve：不传")

    memory_id: str = Field(..., description="memory id")

    workspace_id: str = Field("", description="workspace id")

    api_key: str = Field("", description="api id")

    scene: str = Field("", description="需要枚举来源: TONGYI_MAIN_CHAT, TONGYI_CHAR_CHAT, BAILIAN, ASSISTANT_API")

    algo_version: str = Field("", description="算法版本，只在做AB实验时透传")

    output_max_count: int = Field(3, description="retrieve时最多的条数，约定3-10条")

    user_profile: List[UserAttribute] = Field([], description="user_profile")

    ext_info: Dict[str, str] = Field({}, description="extra information")
