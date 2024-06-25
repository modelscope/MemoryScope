from memory_scope.enumeration.language_enum import LanguageEnum


INFO_FILTER_SYSTEM_PROMPT = {
    LanguageEnum.CN: """
任务指令：对所给{batch_size}个句子中所含有的关于用户的信息打分，分数为0,1,2或3。
注意：其中0表示不包含用户信息，1表示句子中只包含用户假设的信息或者用户虚构的内容，2表示包含用户的一般信息，时效性信息或者需要猜测才能得到的用户信息，3表示明确含有或者可以确定推断出关于用户的重要信息，或者用户要求记录。
按如下格式输出, 每一行输出一个打分，一定加<>，一共输出{batch_size}个分数:
结果：
<分数:0或1或2或3>
""",
    LanguageEnum.EN: """
"""
}


