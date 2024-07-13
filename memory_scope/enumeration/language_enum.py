from enum import Enum


class LanguageEnum(str, Enum):
    """
    An enumeration representing supported languages.
    
    Members:
        - CN: Represents the Chinese language.
        - EN: Represents the English language.
    """
    CN = "cn"

    EN = "en"
