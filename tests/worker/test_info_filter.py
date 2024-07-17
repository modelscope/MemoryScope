import unittest

from memory_scope.cli import MemoryScope
from memory_scope.constants.common_constants import CHAT_MESSAGES, NEW_OBS_NODES
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.message import Message
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.tool_functions import init_instance_by_config


class TestInfoFilter(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        ms = MemoryScope().load_config("config/demo_config_cn.yaml")
        ms.init_global_content_by_config()

    @unittest.skip
    def test_info_filter_cn(self):
        name = "info_filter"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=G_CONTEXT.worker_config[name],
            suffix_name="worker",
            name=name,
            is_multi_thread=False,
            context={},
            context_lock=None,
            thread_pool=G_CONTEXT.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="我爱吃川菜"),
            Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃苹果"),
            Message(role=MessageRoleEnum.USER.value, content="明天我要去高考"),
        ]

        worker.set_context(CHAT_MESSAGES, chat_messages)
        worker.run()

        result = [msg.content for msg in worker.chat_messages]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    def test_get_observation_cn(self):
        name = "get_observation"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=G_CONTEXT.worker_config[name],
            suffix_name="worker",
            name=name,
            is_multi_thread=False,
            context={},
            context_lock=None,
            thread_pool=G_CONTEXT.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="我爱吃川菜"),
            Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃苹果"),
            Message(role=MessageRoleEnum.USER.value, content="我准备去高考"),
            Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃西瓜"),
            Message(role=MessageRoleEnum.USER.value, content="我在一家叫京东的公司干活"),
        ]

        # chat_messages = [
        #     Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃西瓜"),
        #     Message(role=MessageRoleEnum.USER.value, content="我在一家叫京东的公司干活"),
        # ]

        worker.set_context(CHAT_MESSAGES, chat_messages)
        worker.run()

        result = [node.content for node in worker.memory_handler.get_memories(NEW_OBS_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")
