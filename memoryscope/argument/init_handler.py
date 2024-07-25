class InitializationHandler(object):

    def __init__(self):
        self.file_path: str = __file__

        self.global_config_dict: dict = {}

        self.memory_chat_dict: dict = {}

        self.memory_service_dict: dict = {}

        self.worker_dict: dict = {}

        self.model_dict: dict = {}

        self.memory_store: dict = {}

        self.monitor: dict = {}

    def update_by_arguments(self):
        pass

    def load_from_config(self):
        pass


    def load_from_file(self):
        pass
