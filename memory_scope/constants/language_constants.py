from memory_scope.enumeration.language_enum import LanguageEnum

DATATIME_WORD_LIST = {
    LanguageEnum.CN:
        [
            "天",
            "周",
            "月",
            "年",
            "星期",
            "点",
            "分钟",
            "小时",
            "秒",
            "上午",
            "下午",
            "早上",
            "早晨",
            "晚上",
            "中午",
            "日",
            "夜",
            "清晨",
            "傍晚",
            "凌晨",
            "岁",
        ],
    LanguageEnum.EN: [

    ]
}

WEEKDAYS = {
    LanguageEnum.CN: [
        "周一",
        "周二",
        "周三",
        "周四",
        "周五",
        "周六",
        "周日"
    ],
    LanguageEnum.EN: [

    ]
}

NONE_WORD = {
    LanguageEnum.CN: "无",
    LanguageEnum.EN: "none"
}

REPEATED_WORD = {
    LanguageEnum.CN: "重复",
    LanguageEnum.EN: "repeated"
}

CONTRADICTORY_WORD = {
    LanguageEnum.CN: "矛盾",
    LanguageEnum.EN: "contradictory"
}

INCLUDED_WORD = {
    LanguageEnum.CN: "被包含",
    LanguageEnum.EN: "included"
}

COLON_WORD = {
    LanguageEnum.CN: "：",
    LanguageEnum.EN: ":"
}
