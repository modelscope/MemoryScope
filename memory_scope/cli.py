import fire

from memory_scope.chat.memory_chat import MemoryChat
from memory_scope.handler.config_handler import ConfigHandler

"""
1. fire read config
2. init config
    1. global configs: global + db + llm + monitor
    2. worker config list: worker + llm
3. init db
4. init workers, global+worker
5. init llms
6. init monitor
7. new Agent,add db workers llms monitor
    1. new memory service
        1. new pipeline
    2. chat
    3. 
"""


def main(config_path: str):
    config_handler = ConfigHandler(config_path)

    agent = MemoryChat()
    agent.run()


if __name__ == "__main__":
    fire.Fire(main)
