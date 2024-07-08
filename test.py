from memory_scope.cli import CliJob


def main(config_path: str):
    job = CliJob()
    job.run(config=config_path)


if __name__ == "__main__":
    # fire.Fire(main)
    main("config/config.yaml")
