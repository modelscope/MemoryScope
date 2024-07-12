from enum import Enum


class MemoryNodeStatus(str, Enum):
    """
    Enumeration representing various statuses of a memory node.
    
    Each status reflects a different state of the node in terms of its lifecycle or content:
    - NEW: Indicates a newly created node.
    - MODIFIED: Signifies that the node has been altered.
    - CONTENT_MODIFIED: Specifies changes in the actual content of the node.
    - ACTIVE: Denotes that the node is currently in use or accessible.
    - EXPIRED: Implies that the node is no longer valid or needed.
    """
    NEW = "new"
    MODIFIED = "modified"
    CONTENT_MODIFIED = "content_modified"
    ACTIVE = "active"
    EXPIRED = "expired"
