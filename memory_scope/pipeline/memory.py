from typing import List, Dict

from pydantic import Field

from model.message import Message
from model.user_attribute import UserAttribute
from request.base_model import RequestBaseModel

class MemoryServiceRequestModel(RequestBaseModel):
    user: UserConfig = None

    messages: List[Message] = Field(...,
                                    description="summary: 多轮对话的list,默认按照时间正序，最后一条是最新的; retrieve: 最后一条是query")

    messages_pick_n: int = Field(1, description="summary：传需要总结的msg的个数;retrieve：不传")
