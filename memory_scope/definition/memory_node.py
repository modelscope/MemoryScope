from typing import Dict, List

from pydantic import Field, BaseModel


class MemoryNode(BaseModel):
    id: str = Field("", description="uuid64")

    content: str = Field("", description="memory content")

    memoryId: str = Field("", description="unique memory id")

    memoryType: str = Field("", description="conversation/observation/insight...")

    metaData: Dict[str, str] = Field({}, description="other data infos")

    status: str = Field("active", description="active or expired")

    vector: List[float] = Field([], description="content embedding result, return empty")
