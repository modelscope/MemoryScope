# 使用argparse库的示例
import argparse


def main():
    parser = argparse.ArgumentParser(description="示例CLI程序")
    parser.add_argument('--echo', help="输出传入的消息")

    args = parser.parse_args()
    if args.echo:
        print(f"收到的消息: {args.echo}")


if __name__ == "__main__":
    main()
