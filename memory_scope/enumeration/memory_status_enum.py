from enum import Enum


class MemoryNodeStatus(str, Enum):
    ACTIVE = "active"

    EXPIRED = "expired"
