# common_constants.py
# This module defines constants used as keys throughout the application to maintain a consistent reference 
# for data structures related to workflow management, chat interactions, context storage, memory operations, 
# node processing, and temporal inference functionalities.

WORKFLOW_NAME = "workflow_name"
"""
The constant represents the key for the name of the workflow in the application context.
"""

RESULT = "result"
"""
Indicates the key for storing the result of an operation or processing within the application.
"""

CHAT_MESSAGES = "chat_messages"
"""
Used as the key for accessing or storing a collection of chat messages in the application's data model.
"""

CONTEXT_MEMORY_DICT = "context_memory_dict"
"""
Denotes the key for a dictionary that holds contextual memory information, which might be utilized for maintaining conversation context.
"""

CHAT_KWARGS = "chat_kwargs"
"""
Key for passing keyword arguments specifically related to chat functionalities.
"""

QUERY_WITH_TS = "query_with_ts"
"""
Refers to a query operation that includes a timestamp, used when retrieving data with temporal consideration.
"""

RETRIEVE_MEMORY_NODES = "retrieve_memory_nodes"
"""
Specifies the action of retrieving nodes from the memory, often used in the context of information retrieval processes.
"""

RANKED_MEMORY_NODES = "ranked_memory_nodes"
"""
Indicates a collection of memory nodes that have been ranked, typically by relevance or other criteria.
"""

NOT_REFLECTED_NODES = "not_reflected_nodes"
"""
Represents nodes that have not been incorporated or reflected back into the system, such as unprocessed updates.
"""

NOT_UPDATED_NODES = "not_updated_nodes"
"""
Identifies nodes that were not updated during a processing cycle, useful for tracking changes.
"""

EXTRACT_TIME_DICT = "extract_time_dict"
"""
A key pointing to a dictionary used for extracting or storing time-related information extracted from data nodes.
"""

NEW_OBS_NODES = "new_obs_nodes"
"""
Refers to nodes representing new observations added to the system.
"""

NEW_OBS_WITH_TIME_NODES = "new_obs_with_time_nodes"
"""
Similar to 'new_obs_nodes', but specifically denotes these observations are associated with timestamps.
"""

INSIGHT_NODES = "insight_nodes"
"""
Key for nodes that encapsulate insights derived from data analysis or processing stages.
"""

TODAY_NODES = "today_nodes"
"""
Indicates nodes relevant or generated on the current day, assisting in daily summaries or time-sensitive operations.
"""

MERGE_OBS_NODES = "merge_obs_nodes"
"""
Specifies nodes that are candidates for merging, often to consolidate similar or redundant observations.
"""

TIME_INFER = "time_infer"
"""
Involves the process of inferring time information from data, crucial for temporal understanding within the application.
"""
