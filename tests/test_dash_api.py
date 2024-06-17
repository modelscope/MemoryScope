import sys


sys.path.append(".")
from common.dash_embedding_client import DashEmbeddingClient
from common.dash_generate_client import DashGenerateClient
from common.dash_rerank_client import DashReRankClient
from enumeration.env_type import EnvType

KEY = "sk-fc77951df1d94418bb5a6cd84da76b17"


def test_emb():
    client = DashEmbeddingClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    result = client.call(text="今天你吃饭了吗？")
    print(len(result))
    print(result[:10])


def test_gen():
    client = DashGenerateClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    # result = client.call("今天你吃饭了吗？")
    messages = [{'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': '今天你吃饭了吗？'}]
    result = client.call(messages=messages)
    print(result)


def test_rerank():
    query = "什么是文本排序模型"
    documents = [
        "文本排序模型广泛用于搜索引擎和推荐系统中，它们根据文本相关性对候选文本进行排序",
        "量子计算是计算科学的一个前沿领域",
        "预训练语言模型的发展给文本排序模型带来了新的进展"
    ]
    client = DashReRankClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    result = client.call(query=query, documents=documents)
    print(result)


def test_rerank2():
    query = "工作地址"
    documents = [
        "我在阿里工作",
    ]
    client = DashReRankClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    result = client.call(query=query, documents=documents)
    print(result)
    result2 = client.call(query=documents[0], documents=[query])
    print(result2)


def test_gen2():
    client = DashGenerateClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    # result = client.call("今天你吃饭了吗？")
    messages = [{'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': '今天你吃饭了吗？'}]
    # print(client.call(messages=messages))
    print(client.call(messages=messages, model_name="deepseek-7b-chat"))
    print(client.call(messages=messages, model_name="qwen1.5-7b-chat"))
    print(client.call(messages=messages, model_name="qwen1.5-4b-chat"))
    print(client.call(messages=messages, model_name="baichuan2-7b-chat-v1"))
    print(client.call(messages=messages, model_name="qwen-max"))
    print(client.call(messages=messages, model_name="qwen-plus"))


def test_gen3():
    messages = [{'role': 'system',
                 'content': '任务：从下面每一行的信息中提取出关于用户的可以挖掘的最多1个最重要的用户画像属性，每个<用户画像属性>最多4个字。\n注意：<用户画像属性>可能是一般的用户偏好，也可能是运动偏好，旅游偏好，饮食偏好等等，也可以是重要事件性质，比如最近重要的事情，也可以是一些高度概括的人生理想，价值观，人生观，性格等等。\n要求：根据<用户画像属性>，是可以从下面的信息中提取对应的信息的。\n一定要按如下格式输出，最后的结果一定要加<>:\n<序号> <用户画像属性>'},
                {'role': 'user',
                 'content': '\n任务：从下面每一行的信息中提取出关于用户的可以挖掘的最多1个最重要的用户画像属性，每个<用户画像属性>最多4个字。\n注意：<用户画像属性>可能是一般的用户偏好，也可能是运动偏好，旅游偏好，饮食偏好等等，也可以是重要事件性质，比如最近重要的事情，也可以是一些高度概括的人生理想，价值观，人生观，性格等等。\n要求：根据<用户画像属性>，是可以从下面的信息中提取对应的信息的。\n一定要按如下格式输出，最后的结果一定要加<>:\n<序号> <用户画像属性>\n\n示例1\n信息：\n用户想知道明天上海的天气情况。\n用户可能在上海工作，并关心是否需要带伞上班。\n用户在阿里巴巴徐汇滨江园区附近工作。\n用户计划中午在公司附近用餐。\n用户对咖啡因过敏。\n用户喝了咖啡后晚上会出现失眠的情况。\n用户偏好口味较为清淡、不辣的中餐馆。\n用户刚开始了他们的第一份工作。\n用户的工作岗位是阿里巴巴的算法工程师。\n用户希望得到与该岗位相关的职场建议。\n用户面临的问题是在项目进展初期如何有效与上司沟通。\n用户的目标是及时同步项目状态给上司。\n用户希望了解image generation（图像生成）技术的发展概览和最新进展。\n用户对variational auto-encoder、GAN、Diffusion Model等技术及其相互关系感兴趣。\n问题：\n<1> <饮食偏好>\n<2> <技术方向>\n\n示例2\n信息：\n用户想要了解如何使用torchvision库来可视化深度学习任务的进度信息。\n用户希望了解如何将基于numpy和pytorch的并行计算方案迁移到CUDA支持的GPU上运行。\n用户询问是否需要依赖特定的包来完成这一任务。\n用户希望了解如何在Python中自定义进程和线程以实现并行计算。\n用户在编程中遇到了与并行计算相关的问题。\n用户希望学习如何使用Python（numpy，pytorch）在GPU上实现简单的并行计算。\n用户希望了解并行计算的基本概念，包括threads。\n用户询问有关世界各地著名菜系的信息。\n用户对全球各地的美食非常感兴趣。\n用户在寻求有关推拿按摩手法的教程或相关网站推荐。\n用户希望系统地学习正规的推拿按摩手法。\n用户对按摩感兴趣，并且经常去推拿按摩店。\n用户想了解自己在静息状态下一小时大概会消耗多少大卡热量。\n用户年龄为28岁。\n用户体重为70kg。\n用户是男性。\n用户关心其体重与运动消耗的额外热量及心率之间的关系。\n用户在询问为了实现这一目标，每天需要额外消耗多少大卡热量。\n用户希望每月减重1kg。\n用户希望得到类似战略类手机游戏的推荐。\n用户喜欢玩三国志系列、文明系列、全面战争、骑马与砍杀等战略类游戏。\n用户希望根据他们的喜好获得新的游戏推荐。\n用户列举了他们喜欢的具体游戏类型，包括：三国志系列、文明系列、全面战争、骑马与砍杀等。\n用户喜欢玩战略类游戏。\n问题：\n<1> <游戏偏好>\n<2> <运动计划>\n<3> <技术方向>\n\n示例3\n信息：\n用户寻求推荐一个相关课程或网址以进行学习。\n用户计划去青岛旅游。\n用户正为张三的女儿选购生日礼物。\n用户请求为一位名叫张三的人的女儿撰写一段温馨的祝福语。\n用户的同事名叫张三。\n用户与张三约定讨论阿里云百炼项目。\n用户与同事张三讨论了该项目的PRD（产品需求文档）。\n同事张三计划下周对PRD进行最终确定。\n张三还安排了在再下一周进行POC（Proof of Concept，概念验证）的讨论。\n用户希望获知该项目工程开发工作的负责团队信息，以了解项目执行的组织架构与分工情况。\n问题：\n<1> <张三关系>\n\n信息：\n用户对策略游戏感兴趣，希望寻找新的挑战。\n用户近期感到工作压力大，寻求放松方法。\n用户在上海有几位常聚的朋友。\n用户考虑更换工作，关注上海哪些区的工作机会较多。\n用户热衷于尝试新美食，求推荐美食应用。\n用户喜欢自己烹饪，需要海鲜菜谱推荐。\n用户想了解维持广泛社交关系的方法。\n问题：\n'}]
    prompt = """
任务：从下面每一行的信息中提取出关于用户的可以挖掘的最多1个最重要的用户画像属性，每个<用户画像属性>最多4个字。
注意：<用户画像属性>可能是一般的用户偏好，也可能是运动偏好，旅游偏好，饮食偏好等等，也可以是重要事件性质，比如最近重要的事情，也可以是一些高度概括的人生理想，价值观，人生观，性格等等。
要求：根据<用户画像属性>，是可以从下面的信息中提取对应的信息的。
一定要按如下格式输出，最后的结果一定要加<>:
<序号> <用户画像属性>
        
示例1
信息：
用户想知道明天上海的天气情况。
用户可能在上海工作，并关心是否需要带伞上班。
用户在阿里巴巴徐汇滨江园区附近工作。
用户计划中午在公司附近用餐。
用户对咖啡因过敏。
用户喝了咖啡后晚上会出现失眠的情况。
用户偏好口味较为清淡、不辣的中餐馆。
用户刚开始了他们的第一份工作。
用户的工作岗位是阿里巴巴的算法工程师。
用户希望得到与该岗位相关的职场建议。
用户面临的问题是在项目进展初期如何有效与上司沟通。
用户的目标是及时同步项目状态给上司。
用户希望了解image generation（图像生成）技术的发展概览和最新进展。
用户对variational auto-encoder、GAN、Diffusion Model等技术及其相互关系感兴趣。
问题：
<1> <饮食偏好>
<2> <技术方向>
示例2
信息：
用户想要了解如何使用torchvision库来可视化深度学习任务的进度信息。
用户希望了解如何将基于numpy和pytorch的并行计算方案迁移到CUDA支持的GPU上运行。
用户询问是否需要依赖特定的包来完成这一任务。
用户希望了解如何在Python中自定义进程和线程以实现并行计算。
用户在编程中遇到了与并行计算相关的问题。
用户希望学习如何使用Python（numpy，pytorch）在GPU上实现简单的并行计算。
用户希望了解并行计算的基本概念，包括threads。
用户询问有关世界各地著名菜系的信息。
用户对全球各地的美食非常感兴趣。
用户在寻求有关推拿按摩手法的教程或相关网站推荐。
用户希望系统地学习正规的推拿按摩手法。
用户对按摩感兴趣，并且经常去推拿按摩店。
用户想了解自己在静息状态下一小时大概会消耗多少大卡热量。
用户年龄为28岁。
用户体重为70kg。
用户是男性。
用户关心其体重与运动消耗的额外热量及心率之间的关系。
用户在询问为了实现这一目标，每天需要额外消耗多少大卡热量。
用户希望每月减重1kg。
用户希望得到类似战略类手机游戏的推荐。
用户喜欢玩三国志系列、文明系列、全面战争、骑马与砍杀等战略类游戏。
用户希望根据他们的喜好获得新的游戏推荐。
用户列举了他们喜欢的具体游戏类型，包括：三国志系列、文明系列、全面战争、骑马与砍杀等。
用户喜欢玩战略类游戏。
问题：
<1> <游戏偏好>
<2> <运动计划>
<3> <技术方向>
示例3
信息：
用户寻求推荐一个相关课程或网址以进行学习。
用户计划去青岛旅游。
用户正为张三的女儿选购生日礼物。
用户请求为一位名叫张三的人的女儿撰写一段温馨的祝福语。
用户的同事名叫张三。
用户与张三约定讨论阿里云百炼项目。
用户与同事张三讨论了该项目的PRD（产品需求文档）。
同事张三计划下周对PRD进行最终确定。
张三还安排了在再下一周进行POC（Proof of Concept，概念验证）的讨论。
用户希望获知该项目工程开发工作的负责团队信息，以了解项目执行的组织架构与分工情况。
问题：
<1> <张三关系>
信息：
用户对策略游戏感兴趣，希望寻找新的挑战。
用户近期感到工作压力大，寻求放松方法。
用户在上海有几位常聚的朋友。
用户考虑更换工作，关注上海哪些区的工作机会较多。
用户热衷于尝试新美食，求推荐美食应用。
用户喜欢自己烹饪，需要海鲜菜谱推荐。
用户想了解维持广泛社交关系的方法。
问题：
    """
    client = DashGenerateClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    result = client.call(prompt=prompt.strip(), model_name="qwen-max", seed=0, top_k=1,
                         repetition_penalty=10)  # seed=10, repetition_penalty=0.001
    # print(client.call(prompt=content, model_name="qwen-plus"))
    print(result)


def test_rerank3():
    """
用户喜欢在家做饭，需海鲜菜谱推荐。 score=0.33822810090097916
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户喜欢在家做饭，求推荐海鲜菜谱。 score=0.3285956750439506
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户喜欢烹饪，特别是寻找海鲜菜谱。 score=0.2792495470520024
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户热爱烹饪新鲜海鲜，积极寻找美食应用和菜谱。 score=0.19372969292115966
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户喜爱探索新美食与在家烹饪海鲜。 score=0.1566147836382108
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户拥有几位要好朋友，常共同外出就餐。 score=0.14541493132600777
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户有几位常聚餐的好友。 score=0.11955426943198397
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户关注上海生活信息，包括寻找新鲜海鲜地点及询问工作机会多的区域。 score=0.08339651657739067
2024-05-31 16:49:19 INFO jinli_05 semantic_rerank_worker:67] content=用户饮食偏好 (喜欢吃什么菜): 海鲜） score=0.08032847382954839


    """
    query = "用户喜欢吃什么菜"
    # query = "运动"
    documents = [
        "用户喜欢在家做饭，求推荐海鲜菜谱。",
        "用户饮食偏好 (喜欢吃什么菜): 海鲜）。",
        "用户好奇打篮球是否能促进身高增长。",
        "用户感到在上海的工作压力大，寻求放松方法。",
    ]
    client = DashReRankClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    result = client.call(query=query, documents=documents)
    print(result)
    # result1 = client.call(query=documents[0], documents=[query])
    # result2 = client.call(query=documents[1], documents=[query])
    # result3 = client.call(query=documents[2], documents=[query])
    # result4 = client.call(query=documents[3], documents=[query])
    # print(result1)
    # print(result2)
    # print(result3)
    # print(result4)


def test_gen4():
    messages = [{'role': 'system',
                 'content': """
任务：从下面的信息中提取出关于用户的可以挖掘的最多3个重要的用户属性，每个用户属性最多4个字。
注意：用户属性可能是一般的用户偏好，也可能是运动偏好，旅游偏好，饮食偏好等等，也可以是重要事件性质，比如最近重要的事情，也可以是一些高度概括的人生理想，价值观，人生观，性格等等。
要求：根据用户属性，我们可以生成“用户的<用户属性>是什么？”的问题，以此从下面的信息中提取用户属性对应的值。
每一行输出一个<用户属性>:
<用户属性>
                 """.strip()
                 },
                {'role': 'user',
                 'content': """
示例1
信息：
用户想知道明天上海的天气情况。
用户可能在上海工作，并关心是否需要带伞上班。
用户在阿里巴巴徐汇滨江园区附近工作。
用户计划中午在公司附近用餐。
用户对咖啡因过敏。
用户喝了咖啡后晚上会出现失眠的情况。
用户偏好口味较为清淡、不辣的中餐馆。
用户刚开始了他们的第一份工作。
用户的工作岗位是阿里巴巴的算法工程师。
用户希望得到与该岗位相关的职场建议。
用户面临的问题是在项目进展初期如何有效与上司沟通。
用户的目标是及时同步项目状态给上司。
用户希望了解image generation（图像生成）技术的发展概览和最新进展。
用户对variational auto-encoder、GAN、Diffusion Model等技术及其相互关系感兴趣。
问题：
饮食偏好
技术方向

示例2
信息：
用户想要了解如何使用torchvision库来可视化深度学习任务的进度信息。
用户希望了解如何将基于numpy和pytorch的并行计算方案迁移到CUDA支持的GPU上运行。
用户询问是否需要依赖特定的包来完成这一任务。
用户希望了解如何在Python中自定义进程和线程以实现并行计算。
用户在编程中遇到了与并行计算相关的问题。
用户希望学习如何使用Python（numpy，pytorch）在GPU上实现简单的并行计算。
用户希望了解并行计算的基本概念，包括threads。
用户询问有关世界各地著名菜系的信息。
用户对全球各地的美食非常感兴趣。
用户在寻求有关推拿按摩手法的教程或相关网站推荐。
用户希望系统地学习正规的推拿按摩手法。
用户对按摩感兴趣，并且经常去推拿按摩店。
用户想了解自己在静息状态下一小时大概会消耗多少大卡热量。
用户年龄为28岁。
用户体重为70kg。
用户是男性。
用户关心其体重与运动消耗的额外热量及心率之间的关系。
用户在询问为了实现这一目标，每天需要额外消耗多少大卡热量。
用户希望每月减重1kg。
用户希望得到类似战略类手机游戏的推荐。
用户喜欢玩三国志系列、文明系列、全面战争、骑马与砍杀等战略类游戏。
用户希望根据他们的喜好获得新的游戏推荐。
用户列举了他们喜欢的具体游戏类型，包括：三国志系列、文明系列、全面战争、骑马与砍杀等。
用户喜欢玩战略类游戏。
问题：
游戏偏好
运动计划
技术方向

示例3
信息：
用户寻求推荐一个相关课程或网址以进行学习。
用户计划去青岛旅游。
用户正为张三的女儿选购生日礼物。
用户请求为一位名叫张三的人的女儿撰写一段温馨的祝福语。
用户的同事名叫张三。
用户与张三约定讨论阿里云百炼项目。
用户与同事张三讨论了该项目的PRD（产品需求文档）。
同事张三计划下周对PRD进行最终确定。
张三还安排了在再下一周进行POC（Proof of Concept，概念验证）的讨论。
用户希望获知该项目工程开发工作的负责团队信息，以了解项目执行的组织架构与分工情况。
问题：
朋友关系

任务：从下面的信息中提取出关于用户的可以挖掘的最多3个重要的用户属性，每个用户属性最多4个字。
注意：用户属性可能是一般的用户偏好，也可能是运动偏好，旅游偏好，饮食偏好等等，也可以是重要事件性质，比如最近重要的事情，也可以是一些高度概括的人生理想，价值观，人生观，性格等等。
要求：根据用户属性，我们可以生成“用户的<用户属性>是什么？”的问题，以此从下面的信息中提取用户属性对应的值。
每一行输出一个<用户属性>:
<用户属性>

信息：
用户想知道上海哪里的海鲜最新鲜，表明用户在上海生活或访问，并对食物品质有要求。
用户寻找策略游戏推荐，显示出对策略类游戏的兴趣和寻求新挑战的愿望。
用户提到在上海的工作压力大，寻求放松建议，反映了其当前的生活压力状态和对减压方法的需求。
用户拥有常一起吃饭的好友，强调了其社交活动和对友谊的重视。
用户考虑更换工作，关注上海哪些区工作机会多，表明职业规划上的变动意向。
用户喜欢尝试新美食并询问美食应用推荐，再次强调对美食的兴趣和探索欲。
用户提到了自己烹饪的兴趣，特别是对海鲜菜谱的需求，细化了其个人爱好。
用户询问维持广泛社交关系的方法，显示其对社交网络维护的关注。
问题：
                 """.strip()
                 }]
    client = DashGenerateClient(authorization=KEY, request_id="", dash_scope_uid="", workspace="")
    # result = client.call(messages=messages, model_name="qwen-long", seed=0, top_k=1)
    result = client.call(messages=messages, model_name="qwen-max", seed=0, top_k=1)
    # result = client.call(messages=messages, model_name="qwen-max", seed=0)

    # seed=10, repetition_penalty=0.001
    print(result)


def test_gen_time():
    prompt = "任务指令：从语句与语句发生的时间，推断并提取语句内容中指向的时间段。回答尽可能完整的时间段。\n语句：好像是前天有人来找过你。\n时间：2074年12月7日，2074年第49周，周三，16时30分0秒。\n回答："
    # 1656375133437235, 197291
    client = DashGenerateClient(authorization="sk-AdrklI1sWM", request_id="",
                                dash_scope_uid="", workspace="", env_type=EnvType.DAILY)
    # result = client.call(messages=messages, model_name="qwen-long", seed=0, top_k=1)
    result = client.call(prompt=prompt, model_name="qwen_1_8_parse_time_service", seed=0, top_k=1)
    # result = client.call(messages=messages, model_name="qwen-max", seed=0)

    # seed=10, repetition_penalty=0.001
    print(result)


if __name__ == "__main__":
    # test_emb()
    # test_gen()
    # test_rerank()
    # test_rerank2()
    # test_gen2()
    # test_gen3()
    # test_gen4()
    # test_rerank3()
    test_gen_time()
