from enum import Enum


class ActionStatusEnum(str, Enum):
    """
    Enumeration representing various statuses of a memory node.
    
    Each status reflects a different state of the node in terms of its lifecycle or content:
    - NEW: Indicates a newly created node.
    - MODIFIED: Signifies that the node has been altered.
    - CONTENT_MODIFIED: Specifies changes in the actual content of the node.
    - NONE: do nothing.
    - DELETE: delete memories.
    """
    NEW = "new"

    MODIFIED = "modified"

    CONTENT_MODIFIED = "content_modified"

    NONE = "none"

    DELETE = "delete"
