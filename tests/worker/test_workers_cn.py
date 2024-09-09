import datetime
import unittest

from memoryscope.constants.common_constants import NEW_OBS_NODES, NEW_OBS_WITH_TIME_NODES, \
    MERGE_OBS_NODES, QUERY_WITH_TS, EXTRACT_TIME_DICT, NOT_REFLECTED_NODES, INSIGHT_NODES, NOT_UPDATED_NODES, \
    MEMORYSCOPE_CONTEXT, CHAT_MESSAGES_SCATTER, TARGET_NAME
from memoryscope.core.config.arguments import Arguments
from memoryscope.core.memoryscope import MemoryScope
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.scheme.memory_node import MemoryNode
from memoryscope.scheme.message import Message


class TestWorkersCn(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        self.arguments = Arguments(
            language="cn",
            human_name="用户",
            assistant_name="AI",
            memory_chat_class="api_memory_chat",
            generation_backend="dashscope_generation",
            generation_model="qwen-max",
            embedding_backend="dashscope_embedding",
            embedding_model="text-embedding-v2",
            rank_backend="dashscope_rank",
            rank_model="gte-rerank",
            enable_ranker=True,
        )
        self.ms = MemoryScope(arguments=self.arguments)

    def tearDown(self):
        self.ms.close()

    @unittest.skip
    def test_extract_time(self):
        name = "extract_time"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        query = "明天我去上海出差"
        query_timestamp = int(datetime.datetime.now().timestamp())
        worker.set_workflow_context(QUERY_WITH_TS, (query, query_timestamp))
        worker.run()

        result = worker.get_workflow_context(EXTRACT_TIME_DICT)
        worker.logger.info(f"result={result}")

    @unittest.skip
    def test_info_filter(self):
        name = "info_filter"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="我爱吃川菜", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我爱中国", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="假设我是秦始皇", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="帮我写个作文", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="肾病怎么治", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我爱吃海鲜", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃苹果", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="明天我要去高考", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="明天我要去北京出差", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我在阿里巴巴工作", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我擅长优化百炼算法模型",
                    role_name=self.arguments.human_name),
        ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = [msg.content for msg in worker.chat_messages_scatter]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    @unittest.skip
    def test_info_filter2(self):
        name = "info_filter"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="你知道北京哪里的海鲜最新鲜吗",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="有没有推荐的策略游戏？最近想找新的挑战。",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="听说篮球运动对身体很好，是真的吗？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="最近在北京的工作压力太大，有什么放松的建议吗？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="说到朋友，我确实有几位很要好的朋友，我们经常一起出去吃饭。",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="对了，最近想换工作，你觉得北京的哪个区工作机会更多？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="听你这么说，我感觉挺有信心的，谢了！",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我很喜欢尝试新的美食，有没有推荐的美食应用？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我有时也喜欢自己在家做饭，你有没有好的海鲜菜谱推荐？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="听说打篮球可以长高，这是真的吗？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我在北京阿里云园区工作",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我是阿里云百炼的工程师",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="最后一个问题，你知道怎么才能维持广泛的社交关系吗？",
                    role_name=self.arguments.human_name),
        ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = [msg.content for msg in worker.chat_messages_scatter]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    @unittest.skip
    def test_get_observation(self):
        name = "get_observation"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="我爱吃川菜", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃苹果", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我准备去高考", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃西瓜", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我不爱吃西瓜", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我在一家叫京东的公司干活",
                    role_name=self.arguments.human_name),
        ]

        # chat_messages = [
        #     Message(role=MessageRoleEnum.USER.value, content="我不喜欢吃西瓜"),
        #     Message(role=MessageRoleEnum.USER.value, content="我在一家叫京东的公司干活"),
        # ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = [node.content for node in worker.memory_manager.get_memories(NEW_OBS_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    @unittest.skip
    def test_get_observation2(self):
        name = "get_observation"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="有没有推荐的策略游戏？最近想找新的挑战。",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="最近在北京的工作压力太大，有什么放松的建议吗？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="说到朋友，我确实有几位很要好的朋友，我们经常一起出去吃饭。",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="对了，最近想换工作，你觉得北京的哪个区工作机会更多？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我很喜欢尝试新的美食，有没有推荐的美食应用？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我有时也喜欢自己在家做饭，你有没有好的海鲜菜谱推荐？",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我在北京阿里云园区工作",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="我是阿里云百炼的工程师",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="最后一个问题，你知道怎么才能维持广泛的社交关系吗？",
                    role_name=self.arguments.human_name),
        ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = [node.content for node in worker.memory_manager.get_memories(NEW_OBS_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    @unittest.skip
    def test_get_observation_with_time(self):
        name = "get_observation_with_time"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="去年我们一起合作了因果推断技术",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="上个月我去了杭州旅游",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="下周我要去高考", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="明天我去北京出差", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="前天我把苹果扔掉了", role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="前天我把苹果扔掉了，我不喜欢吃",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.USER.value, content="明天是我生日", role_name=self.arguments.human_name),
        ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = [node.content for node in worker.memory_manager.get_memories(NEW_OBS_WITH_TIME_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result={result}")

    @unittest.skip
    def test_contra_repeat(self):
        name = "contra_repeat"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="用户在美团干活"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在阿里巴巴工作"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result1 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="用户在京东工作"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在美团干活"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result2 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="用户在京东工作或有工作经验。"),
            MemoryNode(user_name="AI", target_name="用户", content="用户跳槽至openai工作。"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result3 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="我喜欢吃西瓜"),
            MemoryNode(user_name="AI", target_name="用户", content="用户在阿里巴巴干活"),
            MemoryNode(user_name="AI", target_name="用户", content="我不爱吃西瓜"),
            MemoryNode(user_name="AI", target_name="用户", content="我喜欢吃葡萄"),
            MemoryNode(user_name="AI", target_name="用户", content="我爱吃苹果和香蕉"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result4 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        worker.logger.info(f"result1={result1}")
        worker.logger.info(f"result2={result2}")
        worker.logger.info(f"result3={result3}")
        worker.logger.info(f"result4={result4}")

    @unittest.skip
    def test_get_reflection_subject(self):
        name = "get_reflection_subject"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        nodes = [
            MemoryNode(content="用户对策略游戏感兴趣，寻找新挑战。", role_name=self.arguments.human_name),
            MemoryNode(content="用户在北京工作，感到压力大，寻求放松方式。", role_name=self.arguments.human_name),
            MemoryNode(content="用户有要好朋友，常一起外出就餐。", role_name=self.arguments.human_name),
            MemoryNode(content="用户打算换工作，关心北京的工作机会分布。", role_name=self.arguments.human_name),
            MemoryNode(content="用户喜爱尝试新美食，求美食应用推荐。", role_name=self.arguments.human_name),
            MemoryNode(content="用户喜欢在家做饭，寻求海鲜菜谱。", role_name=self.arguments.human_name),
            MemoryNode(content="用户在北京阿里云园区工作。", role_name=self.arguments.human_name),
            MemoryNode(content="用户是阿里云百炼的工程师。", role_name=self.arguments.human_name),
            MemoryNode(content="用户目前的工作是大语言模型的应用开发", role_name=self.arguments.human_name),
            MemoryNode(content="用户想知道维持广泛社交关系的方法。", role_name=self.arguments.human_name),
        ]

        worker.memory_manager.set_memories(NOT_REFLECTED_NODES, nodes)
        worker.memory_manager.set_memories(INSIGHT_NODES, [])
        worker.run()

        result = [node.key for node in worker.memory_manager.get_memories(INSIGHT_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result.get_reflection={result}")
        return worker

    @unittest.skip
    def test_update_insight_worker(self):
        reflection_worker: MemoryBaseWorker = self.test_get_reflection_subject.__wrapped__(self)

        name = "update_insight"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context=reflection_worker.context,
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        nodes = [
            MemoryNode(content="用户喜欢打王者荣耀", role_name=self.arguments.human_name),
        ]
        worker.memory_manager.set_memories(NOT_UPDATED_NODES, nodes)
        worker.run()

        result = [node.content for node in worker.memory_manager.get_memories(INSIGHT_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result.update_insight={result}")

    @unittest.skip
    def test_long_contra_repeat_worker(self):
        name = "long_contra_repeat"

        worker: MemoryBaseWorker = init_instance_by_config(
            config=self.ms.context.worker_conf_dict[name],
            name=name,
            is_multi_thread=False,
            context={MEMORYSCOPE_CONTEXT: self.ms.context, TARGET_NAME: self.arguments.human_name},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms.context.thread_pool)

        nodes = [
            MemoryNode(content="用户对策略游戏感兴趣，寻找新挑战。", role_name=self.arguments.human_name),
            MemoryNode(content="用户在北京工作，感到压力大，寻求放松方式。", role_name=self.arguments.human_name),
            MemoryNode(content="用户在上海工作。", role_name=self.arguments.human_name),
        ]
        worker.memory_manager.set_memories(NOT_UPDATED_NODES, nodes)
        worker.unit_test_flag = True
        worker.run()

        result = [node.content for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result.long_contra_repeat={result}")

    # @unittest.skip
    def test_example_query_worker(self):
        name = "example_query_worker"

        worker: MemoryBaseWorker = init_instance_by_config(
            config={
                "class": "contrib.example_query_worker",
                "generation_model": "generation_model",
            },
            name=name,
            context={MEMORYSCOPE_CONTEXT: self.ms._context, TARGET_NAME: self.arguments.human_name,
                     "chat_kwargs": {"query": "我一直很爱他们"}},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms._context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="我的两个孩子分别叫小明和小红",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.ASSISTANT.value,
                    content="很高兴认识您和您的家庭成员！小明和小红是非常通俗且好听的名字。",
                    role_name=self.arguments.assistant_name),
            Message(role=MessageRoleEnum.USER.value, content="我一直很爱他们", role_name=self.arguments.human_name),
        ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = worker.get_workflow_context(QUERY_WITH_TS)
        worker.logger.info(f"result={result}")
