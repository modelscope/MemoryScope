from typing import Dict, List

from pydantic import Field, BaseModel


class UserAttribute(BaseModel):
    """
    用户画像的一条属性，和数据库保持一致，只会选择status为1的属性透传过来。
    status会透传过来。
    如果code为空，则为新增，否则是更新。
    确保请求是10条，返回是原始10条+加上新增的条数（如果可以新增）。只会对正确的请求操作数据库。
    """
    code: str = Field("", description="唯一主键 code")

    memory_id: str = Field("", description="memory id")

    # 上游可能没有传这个参数，可能隐藏在memory_id做区分
    scene: str = Field("", description="source: TONGYI_MAIN_CHAT/TONGYI_CHAR_CHAT/BAILIAN/ASSISTANT")

    # 从key改成memory_key
    memory_key: str = Field("", description="memory key")

    value: List[str] = Field([], description="value")

    is_unique: int = Field(1, description="属性是否唯一，if 1 value只有一个，if 0, value 可以很多个")

    is_mutable: int = Field(1, description="是否可变，if 1，value可变，if 1，不可变（用户定义）")

    memory_type: str = Field("", description="profile, profile_customized")

    description: str = Field("", description="memory id")

    status: int = Field(1,
                        description="0为删除，1为active，状态，算法不感知，只为了保存用户删除的画像，给算法传status为valid的用户画像")

    ext_info: Dict[str, str] = Field({}, description="占位符字典")
