from memory_scope.cli import CliJob
import fire


def main(config_path: str):
    job = CliJob(config_path=config_path)
    job.init_global_content_by_config()
    job.run()


if __name__ == "__main__":
    # fire.Fire(main)
    main("config/config.yaml")
