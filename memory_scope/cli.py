# 使用argparse库的示例
import argparse
import fire
from config import C, init
from chat.memory_chat import MemoryChat

def main(config_path:str):
    init(config_path)
    
    agent = MemoryChat()
    agent.run()

if __name__ == "__main__":
    fire.Fire(main)
