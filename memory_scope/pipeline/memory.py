from typing import List, Dict

from pydantic import Field, BaseModel

from node.message import Message
from node.user_attribute import UserAttribute

class MemoryServiceRequestModel(BaseModel):
    user: UserConfig = None

    messages: List[Message] = Field(...,
                                    description="summary: 多轮对话的list,默认按照时间正序，最后一条是最新的; retrieve: 最后一条是query")

    user_profile: List[UserAttribute] = Field([], description="user_profile")

    ext_info: Dict[str, str] = Field({}, description="extra information")

    extra_user_attrs: List = []