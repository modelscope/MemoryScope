from enum import Enum


class StoreStatusEnum(str, Enum):
    VALID = "valid"

    EXPIRED = "expired"
