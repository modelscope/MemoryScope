import datetime
import unittest

from memoryscope.constants.common_constants import CHAT_MESSAGES, NEW_OBS_NODES, NEW_OBS_WITH_TIME_NODES, \
    MERGE_OBS_NODES, QUERY_WITH_TS, EXTRACT_TIME_DICT, NOT_REFLECTED_NODES, INSIGHT_NODES, NOT_UPDATED_NODES, \
    MEMORYSCOPE_CONTEXT, TARGET_NAME, CHAT_MESSAGES_SCATTER
from memoryscope.core.config.arguments import Arguments
from memoryscope.core.memoryscope import MemoryScope
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.scheme.memory_node import MemoryNode
from memoryscope.scheme.message import Message


class TestWorkersEn(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        self.arguments = Arguments(
            language="en",
            human_name="user",
            assistant_name="AI",
            memory_chat_class="api_memory_chat",
            generation_backend="dashscope_generation",
            generation_model="qwen-max",
            embedding_backend="dashscope_embedding",
            embedding_model="text-embedding-v2",
            rank_backend="dashscope_rank",
            rank_model="gte-rerank",
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

        query = "I will be on a business trip to Shanghai tomorrow."
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
            Message(role=MessageRoleEnum.USER.value, content="I love to eat Sichuan cuisine."),
            Message(role=MessageRoleEnum.USER.value, content="I don't like eating apples."),
            Message(role=MessageRoleEnum.USER.value,
                    content="I'm going to take the college entrance examination tomorrow."),
        ]

        worker.set_workflow_context(CHAT_MESSAGES, chat_messages)
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
            Message(role=MessageRoleEnum.USER.value, content="Do you know where the freshest seafood is in Beijing?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="Are there any strategy games you would recommend? I'm looking for a new challenge."),
            Message(role=MessageRoleEnum.USER.value,
                    content="I heard that basketball is good for your health, is that true?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="I’ve been under a lot of work pressure in Beijing lately. Do you have any "
                            "suggestions for relaxing?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="Speaking of friends, I do have a few very good friends and we often go out "
                            "to eat together."),
            Message(role=MessageRoleEnum.USER.value,
                    content="By the way, I want to change jobs recently. Which district in Beijing do you think "
                            "has more job opportunities?"),
            Message(role=MessageRoleEnum.USER.value, content="Hearing you say that, I feel more confident. Thank you!"),
            Message(role=MessageRoleEnum.USER.value,
                    content="I love trying new food, are there any food apps you would recommend?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="I also like to cook at home sometimes. Do you have any good seafood recipes to "
                            "recommend?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="I heard that playing basketball can help you grow taller, is this true?"),
            Message(role=MessageRoleEnum.USER.value, content="I work at Alibaba Cloud in Beijing"),
            Message(role=MessageRoleEnum.USER.value, content="I am an engineer at Alibaba Cloud Bailian"),
            Message(role=MessageRoleEnum.USER.value,
                    content="Last question, do you know how to maintain extensive social relationships?"),
        ]

        worker.set_workflow_context(CHAT_MESSAGES, chat_messages)
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

        # FIXME Does the appearance of 'am' indicate the presence of a time keyword?
        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="I love Sichuan cuisine"),
            Message(role=MessageRoleEnum.USER.value, content="I don't like eating apples"),
            Message(role=MessageRoleEnum.USER.value, content="I am preparing for the college entrance examination"),
            Message(role=MessageRoleEnum.USER.value, content="I don't like eating watermelon"),
            Message(role=MessageRoleEnum.USER.value, content="I don't like watermelon"),
            Message(role=MessageRoleEnum.USER.value, content="I work for a company called JD.com"),
        ]

        worker.set_workflow_context(CHAT_MESSAGES, chat_messages)
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
            Message(role=MessageRoleEnum.USER.value,
                    content="Are there any strategy games you would recommend? I'm looking for a new challenge."),
            Message(role=MessageRoleEnum.USER.value,
                    content="I’ve been under a lot of work pressure in Beijing lately. Do you have any suggestions "
                            "for relaxing?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="Speaking of friends, I do have a few very good friends and we often go out to "
                            "eat together."),
            Message(role=MessageRoleEnum.USER.value,
                    content="By the way, I want to change jobs recently. Which district in Beijing do you think has "
                            "more job opportunities?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="I love trying new food, are there any food apps you would recommend?"),
            Message(role=MessageRoleEnum.USER.value,
                    content="I also like to cook at home sometimes. Do you have any good seafood recipes to "
                            "recommend?"),
            Message(role=MessageRoleEnum.USER.value, content="I work at Alibaba Cloud in Beijing"),
            Message(role=MessageRoleEnum.USER.value, content="I am an engineer at Alibaba Cloud Bailian"),
            Message(role=MessageRoleEnum.USER.value,
                    content="Last question, do you know how to maintain extensive social relationships?"),
        ]

        worker.set_workflow_context(CHAT_MESSAGES, chat_messages)
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
            Message(role=MessageRoleEnum.USER.value,
                    content="Last year we worked together on causal inference technology."),
            Message(role=MessageRoleEnum.USER.value, content="Last month I went to Hangzhou for a trip."),
            Message(role=MessageRoleEnum.USER.value,
                    content="I'm going to take the college entrance examination next week."),
            Message(role=MessageRoleEnum.USER.value, content="I'm going to Beijing on a business trip tomorrow."),
            Message(role=MessageRoleEnum.USER.value, content="I threw away the apple the day before yesterday."),
            Message(role=MessageRoleEnum.USER.value,
                    content="The day before yesterday I threw away the apple. I don't like eating it."),
            Message(role=MessageRoleEnum.USER.value, content="Tomorrow is my birthday."),
        ]

        worker.set_workflow_context(CHAT_MESSAGES, chat_messages)
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
            MemoryNode(user_name="AI", target_name="用户", content="User is working in Meituan"),
            MemoryNode(user_name="AI", target_name="用户", content="User works at Alibaba"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result1 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="User works at JD.com"),
            MemoryNode(user_name="AI", target_name="用户", content="Users working in Meituan"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result2 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="User works at JD.com"),
            MemoryNode(user_name="AI", target_name="用户", content="User is working in Meituan"),
        ]

        worker.memory_manager.set_memories(NEW_OBS_NODES, nodes)
        worker.run()
        result3 = "\n".join([" ".join([node.content, node.store_status, node.action_status])
                             for node in worker.memory_manager.get_memories(MERGE_OBS_NODES)])

        nodes = [
            MemoryNode(user_name="AI", target_name="用户", content="I like to eat watermelon"),
            MemoryNode(user_name="AI", target_name="用户", content="User is working in Alibaba"),
            MemoryNode(user_name="AI", target_name="用户", content="I don't like watermelon"),
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
            MemoryNode(content="Users are interested in strategy games and looking for new challenges."),
            MemoryNode(content="The user works in Beijing, feels stressed, and is looking for ways to relax."),
            MemoryNode(content="The user has good friends and often goes out to eat together."),
            MemoryNode(content="The user is planning to change jobs and is concerned about the distribution of job "
                               "opportunities in Beijing."),
            MemoryNode(content="Users love to try new food and ask for food app recommendations."),
            MemoryNode(content="Users love to cook at home and seek seafood recipes."),
            MemoryNode(content="The user works in the Alibaba Cloud campus in Beijing."),
            MemoryNode(content="The user is an engineer at Alibaba Cloud Bailian."),
            MemoryNode(content="The user's current job is application development of large language models"),
            MemoryNode(content="Users want to know how to maintain extensive social relationships."),
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
            MemoryNode(content="Users like to play King of Glory"),
        ]
        worker.memory_manager.set_memories(NOT_UPDATED_NODES, nodes)
        worker.run()

        result = [node.content for node in worker.memory_manager.get_memories(INSIGHT_NODES)]
        result = "\n".join(result)
        worker.logger.info(f"result.update_insight={result}")

    # @unittest.skip
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
            MemoryNode(content="Users are interested in strategy games and looking for new challenges."),
            MemoryNode(content="The user works in Beijing, feels stressed, and is looking for ways to relax."),
            MemoryNode(content="User works in Shanghai."),
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
                     "chat_kwargs": {"query": "I have always loved them."}},
            context_lock=None,
            memoryscope_context=self.ms.context,
            thread_pool=self.ms._context.thread_pool)

        chat_messages = [
            Message(role=MessageRoleEnum.USER.value, content="My two children are named Xiaoming and Xiaohong.",
                    role_name=self.arguments.human_name),
            Message(role=MessageRoleEnum.ASSISTANT.value,
                    content="I am very pleased to meet you and your family members! Xiaoming and Xiaohong are very pleasant names.",
                    role_name=self.arguments.assistant_name),
            Message(role=MessageRoleEnum.USER.value, content="I have always loved them.",
                    role_name=self.arguments.human_name),
        ]

        worker.set_workflow_context(CHAT_MESSAGES_SCATTER, chat_messages)
        worker.run()

        result = worker.get_workflow_context(QUERY_WITH_TS)
        worker.logger.info(f"result={result}")
