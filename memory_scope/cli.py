import fire

from chat.memory_chat import MemoryChat
from config import init


def main(config_path:str):
    init(config_path)
    
    agent = MemoryChat()
    agent.run()

if __name__ == "__main__":
    fire.Fire(main)
