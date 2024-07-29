from memoryscope.enumeration.language_enum import LanguageEnum

# This dictionary maps languages to lists of words related to datetime expressions.
# It aids in recognizing and processing datetime mentions in text, enhancing the system's ability to understand
# temporal context across different languages.
DATATIME_WORD_LIST = {
    LanguageEnum.CN: [
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
        # Units of Time
        "year", "yr",
        "month", "mo",
        "week", "wk",
        "day", "d",
        "hour", "hr",
        "minute", "min",
        "second", "sec",

        # Days of the Week
        "Monday", "Mon",
        "Tuesday", "Tue", "Tues",
        "Wednesday", "Wed",
        "Thursday", "Thu", "Thur", "Thurs",
        "Friday", "Fri",
        "Saturday", "Sat",
        "Sunday", "Sun",

        # Months of the Year
        "January", "Jan",
        "February", "Feb",
        "March", "Mar",
        "April", "Apr",
        "May", "May",
        "June", "Jun",
        "July", "Jul",
        "August", "Aug",
        "September", "Sep", "Sept",
        "October", "Oct",
        "November", "Nov",
        "December", "Dec",

        # Relative Time References
        "Today",
        "Tomorrow", "Tmrw",
        "Yesterday", "Yday",
        "Now",
        "Morning", "AM", "a.m.",
        "Afternoon", "PM", "p.m.",
        "Evening",
        "Night",
        "Midnight",
        "Noon",

        # Seasonal References
        "Spring",
        "Summer",
        "Autumn", "Fall",
        "Winter",

        # General Time References
        "Century", "cent.",
        "Decade",
        "Millennium",
        "Quarter", "Q1", "Q2", "Q3", "Q4",
        "Semester",
        "Fortnight",
        "Weekend"
    ]
}

# A mapping of weekdays for each supported language, facilitating calendar-related operations and understanding
# within the application.
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
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
}

MONTH_DICT = {
    LanguageEnum.CN: [
        "1月",
        "2月",
        "3月",
        "4月",
        "5月",
        "6月",
        "7月",
        "8月",
        "9月",
        "10月",
        "11月",
        "12月",
    ],
    LanguageEnum.EN: [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
}

# Constants for the word 'none' in different languages
NONE_WORD = {
    LanguageEnum.CN: "无",
    LanguageEnum.EN: "none"
}

# Constants for the word 'repeated' in different languages
REPEATED_WORD = {
    LanguageEnum.CN: "重复",
    LanguageEnum.EN: "repeated"
}

# Constants for the word 'contradictory' in different languages
CONTRADICTORY_WORD = {
    LanguageEnum.CN: "矛盾",
    LanguageEnum.EN: "contradiction"
}

# Constants for the phrase 'included' in different languages
CONTAINED_WORD = {
    LanguageEnum.CN: "被包含",
    LanguageEnum.EN: "contained"
}

# Constants for the symbol ':' in different languages' representations
COLON_WORD = {
    LanguageEnum.CN: "：",
    LanguageEnum.EN: ":"
}

# Constants for the symbol ',' in different languages' representations
COMMA_WORD = {
    LanguageEnum.CN: "，",
    LanguageEnum.EN: ","
}

# Default human name placeholders for different languages
DEFAULT_HUMAN_NAME = {
    LanguageEnum.CN: "用户",
    LanguageEnum.EN: "user"
}

# Mapping of datetime terms from natural language to standardized keys for each supported language
DATATIME_KEY_MAP = {
    LanguageEnum.CN: {
        "年": "year",
        "月": "month",
        "日": "day",
        "周": "week",
        "星期几": "weekday",
    },
    LanguageEnum.EN: {
        "Year": "year",
        "Month": "month",
        "Day": "day",
        "Week": "week",
        "Weekday": "weekday",
    }
}

# Phrase for indicating inferred time in different languages
TIME_INFER_WORD = {
    LanguageEnum.CN: "推断时间",
    LanguageEnum.EN: "Inference time"
}

USER_NAME_EXPRESSION = {
    LanguageEnum.CN: "用户姓名是{name}。",
    LanguageEnum.EN: "User's name is {name}."
}
