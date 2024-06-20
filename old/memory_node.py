import re
from typing import Dict, List

from pydantic import Field, BaseModel


class MemoryNode(BaseModel):
    """
    除了 content_modified，其他均和数据库字段保持统一
    根据code判断，如果code是空，则为新增的memoryNode，如果有值，则为更新
    if content_modified is true，则需要调用embedding服务
    """
    id: str = Field("", description="唯一主键 uuid64")

    code: str = Field("", description="和id保持一致，为空则是新增")

    # 0520新增
    timeCreated: str = Field("", description="Memory创建时间（算法不关注）")

    # 0520新增
    timeModified: str = Field("", description="Memory更新时间（算法不关注）")

    content: str = Field("", description="记忆内容")

    memoryId: str = Field("", description="记忆 id，检索区分字段")

    # 0520新增
    scene: str = Field("", description="source: TONGYI_MAIN_CHAT/TONGYI_CHAR_CHAT/BAILIAN/ASSISTANT")

    # 0520新增
    # NOTE 百炼服务端只召回observation, insight, profile, obs_customized, profile_customized
    memoryType: str = Field("", description="conversation, observation, insight, "
                                            "profile, obs_customized, profile_customized")

    # 0520新增，但不是数据库字段
    content_modified: bool = Field(False, description="content是否被更新，if true，则需要调用embedding服务")

    # reflected: 1 is reflected before, 0 has not reflected, 如果是用户自定义，写入空值"".
    metaData: Dict[str, str] = Field({}, description="元信息: infoScore, algoVersion, datetime, reflected")

    status: str = Field("active", description="active or expired")

    tenantId: str = Field("", description="request id")

    vector: List[float] = Field([], description="content embedding result, return empty")

    def get_time_info(self, time_format: str):
        pattern = re.compile(r'\{([^}]*)}')
        keys = pattern.findall(time_format)

        match_flag = True
        kv_dict = {}
        for k in keys:
            if k not in self.metaData:
                match_flag = False
                break
            v = self.metaData[k]
            if not v:
                match_flag = False
                break

            kv_dict[k] = v

        if match_flag:
            return time_format.format(**kv_dict)
        return ""

    def to_dict(self):
        res = {"content": self.content, "memoryId": self.memoryId, "memoryType": self.memoryType,
               "status": self.status, "metaData": self.metaData}
        return res
