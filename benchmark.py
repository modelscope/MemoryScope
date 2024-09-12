import csv
import ast
from loguru import logger

# Open the CSV file
def read_csv(path):
    with open(path, mode='r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        # Skip the header if your CSV has one
        next(csv_reader)
        res = []
        # Read each row in the CSV
        for row in csv_reader:
            twitter_id, date, tweet = row
            # print(f"Twitter ID: {twitter_id}")
            # print(f"Date: {date}")
            # The tweet is in bytes, so you need to decode it
            tweet = ast.literal_eval(tweet)
            tweet = tweet.decode('utf-8')
            # print(f"Tweet: {tweet}\n")
            res.append({
                "twitter_id": twitter_id,
                "date": date,
                "content": tweet
            })
    return res

tweet_list = read_csv('benchmark/BillGates.csv')
human_name="Bill Gates"

###################################################################################
###################################################################################
###################################################################################

from memoryscope import MemoryScope, Arguments
from rich.console import Console
arguments = Arguments(
    language="cn",
    human_name=human_name,
    assistant_name="AI",
    memory_chat_class="api_memory_chat",
    generation_backend="dashscope_generation",
    generation_model="qwen2-72b-instruct",
    embedding_backend="dashscope_embedding",
    embedding_model="text-embedding-v2",
    rank_backend="dashscope_rank",
    rank_model="gte-rerank",
    enable_ranker=True,
    worker_params={"get_reflection_subject": {"reflect_num_questions": 3}}
)

ms = MemoryScope(arguments=arguments)
msms = ms._context.memory_store.es_store
try: msms.sync_delete_all()
except: pass
msms.log_vector_store_brief()
memory_service = ms.default_memory_service
memory_service.init_service()
memory_chat = ms.default_memory_chat
try: memory_chat.run_service_operation("delete_all")
except: pass


from viztracer import VizTracer

tracer = VizTracer()
tracer.start()

ms._context.memory_store.inject_from_checkpoint("checkpoint_test_dir")
for index, tweet in enumerate(tweet_list):
    query = tweet["content"]
    response = memory_chat.inject_memory(query)
    logger.info(query)
    if index % 20 == 0:
        result = memory_service.consolidate_memory()
        res = memory_chat.run_service_operation("list_memory")
        logger.error(res)
        tracer.save(output_file='result.json')
        ms._context.memory_store.save_checkpoint("checkpoint_test_dir")
tracer.stop()
tracer.save(output_file='result.json')
