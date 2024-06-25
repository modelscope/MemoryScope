from memory_scope.enumeration.language_enum import LanguageEnum


GET_OBSERVATION_SYSTEM_PROMPT = {
    LanguageEnum.CN: """
任务：从下面的{num_obs}句用户句子中依次提取出关于用户的重要信息，与相应的关键词。最多提取{num_obs}条信息。对每一句句子，只提取非常明确的信息和进行非常确定的推断，不要进行任何猜测。
不要重复提取信息，如果句子中的所有信息与前面已经提取出的信息重复了则回答“重复“，如果没有重要信息则回答“无”。注意区分，对于句子中用户假设的信息或者用户虚构的内容，不要提取信息。
对每个句子都做一次信息提取，最后一共输出{num_obs}行信息。
请一定要按如下格式依次输出，最后的结果一定要加<>:
思考：思考的依据和过程，50字以内。
信息：<句子序号> <> <明确的重要信息或“重复”或”无“> <关键词>
""",
    LanguageEnum.EN: """
"""
}

GET_OBSERVATION_FEW_SHOT_PROMPT = {
    LanguageEnum.CN: """
示例1：
用户句子：
1 用户：我现在处境很糟，没有工作，负债几万，怎么办
2 用户：有人说兴趣是最好的老师，也建议兴趣和职业联系起来，但我发现喜欢打篮球的人很多，但靠打篮球成职业的稀少，赚钱的更少，此外，怎么分辨兴趣和喜欢
3 用户：我现在处境很糟，没有工作，负债几万，怎么办
4 用户：我是一个刚毕业的学生，对社会，行业不了解，给我介绍一下社会系统和行业格局
思考：从第1句可以得知用户现在没有工作，负债几万，这是关于用户工作与经济状况的重要信息。
信息：<1> <> <用户当前无工作且负债几万> <无工作, 负债几万>
思考：第2句是用户对他人观点的讨论和疑问，没有明确提及用户个人信息。
信息：<2> <> <无> <>
思考：第3句含有的信息与第1句重复了。
信息：<3> <> <重复> <>
思考：从第4句可以得知用户是一个刚毕业的学生，这是关于用户身份背景状况的重要信息。其余信息重要性不足。
信息：<4> <> <用户是一名刚毕业的学生。> <刚毕业, 学生>

示例2：
用户句子：
1 用户：帮我写一段给同事张三女儿三岁生日的祝福语。
2 用户：能给我整理一张如何使用大模型的技巧列表吗，要求内容尽量精简。
3 用户：两个坏消息，我打羽毛球把拍子打断线了。。。然后我去我朋友家撸猫，结果我猫毛过敏，今天疯狂打喷嚏。。。
4 用户：公元1400年至1550年中国历史大事表。
5 用户：谢啦。我中午在公司附近吃，帮我推荐一家阿里巴巴徐汇滨江园区附近的餐厅吧。
思考：从第1句可以得知张三是用户的同事，这是关于用户的人际关系的重要信息。其余信息重要性不足。
信息：<1> <> <张三是用户的同事。> <张三, 同事>
思考：第2句是用户提出的要求，没有明确提及用户个人信息。
信息：<2> <> <无> <>
思考：从第3句可以得知用户前天打羽毛球时把球拍打断了线，但这不是重要的信息。还可以得知用户对猫毛过敏，这是关于用户的健康的重要信息。
信息：<3> <> <用户对猫毛过敏。> <猫毛, 过敏>
思考：从第4句是用户提出的要求，没有明确提及用户个人信息。
信息：<4> <> <无> <>
思考：从第5句可以得知用户在阿里巴巴徐汇滨江园区工作，这是关于用户的工作地点的重要信息。
信息：<5> <> <用户在阿里巴巴徐汇滨江园区工作。> <阿里巴巴, 徐汇滨江园区, 工作>

示例3：
用户句子：
1 用户：我想买辆新能源汽车，有什么推荐吗？
2 用户：我在上海，想买辆新能源汽车，有什么推荐吗？
3 用户：案外人异议审查期间，人民法院不得对执行标的进行处分，不就是中止执行的意思吗？
4 用户：请写两句藏头诗分别以“胜”和“利”开头。
5 用户：我花5000元买了100股海天味业。
6 用户：李增杰:这个是星座蛙设，但是我是处女座的，我妈感觉因为我的不正常，我妈不让我看了\n雌猴摸了摸李增杰的头，这样啊\n雌猴打开了哔哩哔哩看了看\n雌猴:要不换个设吧，我听你未来的你说，有一个叫难忘的朱古力232这个人，他弄的设是Windows设
思考：从第1句可以得知用户寻求购买新能源汽车的建议或推荐，这是这是关于用户的大宗消费的重要的信息。
信息：<1> <> <用户寻求购买新能源汽车的建议或推荐。> <购买, 新能源汽车>
思考：从第2句可以得知用户当前所在城市为上海，这是关于用户的生活地区的重要信息。其余信息与第1句重复了。
信息：<2> <> <用户所在的城市是上海。> <上海>
思考：第3句是用户对某个观点的讨论和疑问，没有明确提及用户个人信息。
信息：<3> <> <无> <>
思考：第4句是用户提出的要求，没有明确提及用户个人信息。
信息：<4> <> <无> <>
思考：从第5句可以得知用户购买了海天味业股票，购买数量为100股，购买金额为5000元，这是关于用户的投资决策的重要信息。
信息：<5> <> <用户购买了海天味业股票，购买数量为100股，购买金额为5000元。> <海天味业, 股票>
思考：第6句是用户创作的内容，没有明确提及用户个人信息。
信息：<6> <> <无> <>
""",
    LanguageEnum.EN: """
"""
}

GET_OBSERVATION_USER_QUERY_PROMPT = {
    LanguageEnum.CN: """
用户句子：
{user_query}
""",
    LanguageEnum.EN: """
"""
}


