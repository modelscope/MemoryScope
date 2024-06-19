import fire

from memory_scope.job import Job


def main(config_path: str):
    job = Job(config_path=config_path)
    job.init_instance_by_config()
    job.run()


if __name__ == "__main__":
    fire.Fire(main)
