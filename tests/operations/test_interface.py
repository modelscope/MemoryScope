from memory_scope.cli import MemoryScope
from memory_scope.scheme.message import Message

ms = MemoryScope().load_config("config/demo_config_no_stream.yaml")
memory_service = ms.default_service
memory_chat = ms.default_chat_handle

# new_message: Message = Message(role=MessageRoleEnum.USER.value, role_name="我", content="我的爱好是弹琴并且喜欢看电影。")
# memory_service.add_messages(new_message)

res: Message = memory_chat.chat_with_memory(query="我的爱好是弹琴。", remember_response=True)
print(res.message.content)

res: Message = memory_chat.chat_with_memory(query="昨天弹出一个光粒，消灭了星系0x4be。", remember_response=True)
print(res.message.content)

res: Message = memory_chat.chat_with_memory(query="今天弹出一个二向箔，消灭了星系0xa2e。", remember_response=True)
print(res.message.content)
