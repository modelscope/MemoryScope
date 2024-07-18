import unittest

from memory_scope.cli import MemoryScope
from memory_scope.constants.common_constants import CHAT_MESSAGES, NEW_OBS_NODES, NEW_OBS_WITH_TIME_NODES, \
    MERGE_OBS_NODES
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.scheme.message import Message
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.tool_functions import init_instance_by_config


class TestWorkersCn(unittest.TestCase):
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

    @unittest.skip
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
            Message(role=MessageRoleEnum.USER.value, content="我不爱吃西瓜"),
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

    @unittest.skip
    def test_get_observation_with_time_cn(self):
        name = "get_observation_with_time"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=G_CONTEXT.worker_config[name],
            suffix_name="worker",
            name=name,
            is_multi_thread=False,
            context={},
            context_lock=None,
            thread_pool=G_CONTEXT.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="去年我们一起合作了因果推断技术"),
            Message(role=MessageRoleEnum.USER.value, content="上个月我去了杭州旅游"),
            Message(role=MessageRoleEnum.USER.value, content="下周我要去高考"),
            Message(role=MessageRoleEnum.USER.value, content="明天我去北京出差"),
            Message(role=MessageRoleEnum.USER.value, content="前天我把苹果扔掉了"),
            Message(role=MessageRoleEnum.USER.value, content="前天我把苹果扔掉了，我不喜欢吃"),
            Message(role=MessageRoleEnum.USER.value, content="明天是我生日"),
        ]

        worker.set_context(CHAT_MESSAGES, chat_messages)
        worker.run()

        result = [node.content for node in worker.memory_handler.get_memories(NEW_OBS_WITH_TIME_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    # @unittest.skip
    def test_contra_repeat_cn(self):
        name = "contra_repeat"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=G_CONTEXT.worker_config[name],
            suffix_name="worker",
            name=name,
            is_multi_thread=False,
            context={},
            context_lock=None,
            thread_pool=G_CONTEXT.thread_pool)

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="用户在美团干活"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在阿里巴巴工作"),
        ]

        worker.memory_handler.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result1 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_handler.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="用户在京东工作"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在美团干活"),
        ]

        worker.memory_handler.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result2 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_handler.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="用户在京东工作"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在美团干活"),
        ]

        worker.memory_handler.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result3 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_handler.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="我喜欢吃西瓜"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在阿里巴巴干活"),
            MemoryNode(user_name="AI", target_name="用户", content="我不爱吃西瓜"),
        ]

        worker.memory_handler.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result4 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_handler.get_memories(MERGE_OBS_NODES)])

        worker.logger.info(f"result1={result1}")
        worker.logger.info(f"result2={result2}")
        worker.logger.info(f"result3={result3}")
        worker.logger.info(f"result4={result4}")
