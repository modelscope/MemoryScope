from enum import Enum


class MemoryMethodEnum(str, Enum):
    SUMMARY = "summary"

    RETRIEVE = "retrieve"

    RETRIEVE_ALL = "retrieve_all"

    SUMMARY_SHORT = "summary_short"

    SUMMARY_LONG = "summary_long"
