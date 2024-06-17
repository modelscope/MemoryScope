from enum import Enum


class MemoryMethodEnum(str, Enum):
    SUMMARY = "summary"

    RETRIEVE = "retrieve"

    SUMMARY_SHORT = "summary_short"

    SUMMARY_LONG = "summary_long"
