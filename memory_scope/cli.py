import fire

from memory_scope.chat.memory_chat import MemoryChat
from memory_scope.handler.init_handler import InitHandler


def main(config_path: str):
    init_handler = InitHandler(config_path)
    init_handler.init()

    memory_chat = MemoryChat(init_handler)
    memory_chat.chat()


if __name__ == "__main__":
    fire.Fire(main)
