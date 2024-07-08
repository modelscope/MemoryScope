from enum import Enum


class MemoryNodeStatus(str, Enum):
    NEW = "new"

    MODIFIED = "modified"

    CONTENT_MODIFIED = "content_modified"

    ACTIVE = "active"

    EXPIRED = "expired"
