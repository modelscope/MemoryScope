import json
from typing import List, Dict

from enumeration.memory_status_enum import MemoryNodeStatus
from scheme.memory_node import MemoryNode
from node.user_attribute import UserAttribute


class UserProfileHandler(object):
    @classmethod
    def format_content(cls, key: str, description: str, value: str | List[str] = None):
        if not key.startswith("用户"):
            key = f"用户的{key}"

        if not description.startswith("用户"):
            description = f"用户{description}"

        content = f"{key}（{description}）"

        if value:
            if isinstance(value, list):
                value = "，".join(value)
            content = f"{content}：{value}"

        return content

    """
    提供UserAttribute 和 MemoryNode 的相互转化
    """

    @classmethod
    def to_nodes(cls,
                 user_profile: List[UserAttribute] | Dict[str, UserAttribute] | None = None,
                 split_value: bool = False) -> List[MemoryNode]:

        user_profile_dict: Dict[str, UserAttribute] = {}
        if user_profile:
            if isinstance(user_profile, list):
                for user_attr in user_profile:
                    user_profile_dict[user_attr.memory_key] = user_attr
            elif isinstance(user_profile, dict):
                user_profile_dict.update(user_profile)

        user_profile_nodes: List[MemoryNode] = []
        for _, user_attr in user_profile_dict.items():
            # 获取id
            _id = user_attr.code
            if not _id:
                _id = f"{user_attr.memory_id}_{user_attr.scene}_profile_{user_attr.memory_key}"

            attr_node = MemoryNode.init_from_attrs(id=_id,
                                                       code=_id,
                                                       content="",
                                                       memoryId=user_attr.memory_id,
                                                       scene=user_attr.scene,
                                                       memoryType=user_attr.memory_type,
                                                       content_modified=True,
                                                       metaData={
                                                           "memory_key": user_attr.memory_key,
                                                           "value": json.dumps(user_attr.value, ensure_ascii=False),
                                                           "is_unique": str(user_attr.is_unique),
                                                           "is_mutable": str(user_attr.is_mutable),
                                                           "description": user_attr.description,
                                                           "status": MemoryNodeStatus.ACTIVE.value,
                                                           "ext_info": json.dumps(user_attr.ext_info,
                                                                                  ensure_ascii=False),
                                                       },
                                                       status=MemoryNodeStatus.ACTIVE.value)

            if split_value:
                for value in user_attr.value:
                    content = cls.format_content(user_attr.memory_key, user_attr.description, value)
                    attr_node_copy = attr_node.copy(deep=True)
                    attr_node_copy.memory_node.content = content
                    user_profile_nodes.append(attr_node_copy)
            else:
                content = cls.format_content(user_attr.memory_key, user_attr.description, user_attr.value)
                attr_scheme.memory_node.content = content
                user_profile_nodes.append(attr_node)

        return user_profile_nodes

    @classmethod
    def to_user_attr(cls, user_profile_nodes: List[MemoryNode]) -> Dict[str, UserAttribute]:
        user_profile_dict: Dict[str, UserAttribute] = {}

        for node in user_profile_nodes:
            user_attr = UserAttribute(
                code=node.id,
                memory_id=scheme.memory_node.memoryId,
                scene=scheme.memory_node.scene,
                memory_key=scheme.memory_node.metaData["memory_key"],
                value=json.loads(scheme.memory_node.metaData["value"]),
                is_unique=int(scheme.memory_node.metaData["is_unique"]),
                is_mutable=int(scheme.memory_node.metaData["is_mutable"]),
                memory_type=scheme.memory_node.memoryType,
                description=scheme.memory_node.metaData["description"],
                status=1 if scheme.memory_node.metaData["status"] == MemoryNodeStatus.ACTIVE.value else 0,
                ext_info=json.loads(scheme.memory_node.metaData["ext_info"]),
            )
            user_profile_dict[user_attr.memory_key] = user_attr
        return user_profile_dict
