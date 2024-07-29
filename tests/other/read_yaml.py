import sys

sys.path.append(".")  # noqa: E402

from memoryscope.core.utils.prompt_handler import PromptHandler

if __name__ == "__main__":
    file_path: str = __file__
    print(file_path)
    handler = PromptHandler(__file__, language="cn", prompt_file="read_prompt", )
    print(handler.prompt_dict)
