import fire


class CLI:
    def run(self, **kwargs):
        """
        打印传入的 kwargs
        """
        for key, value in kwargs.items():
            print(f"{key}: {value}")


if __name__ == '__main__':
    fire.Fire(CLI().run)
