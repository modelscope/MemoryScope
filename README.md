English | [**中文**](./README_ZH.md)

# MemoryScope
<p align="center">
 <img src="./docs/images/logo.png" alt="MemoryScopeLogo" width="75%">
</p>
Equip your LLM chatbot with a powerful and flexible long term memory system.

[![](https://img.shields.io/badge/python-3.10+-blue)](https://pypi.org/project/memoryscope/)
[![](https://img.shields.io/badge/pypi-v0.1.1.0-blue?logo=pypi)](https://pypi.org/project/memoryscope/)
[![](https://img.shields.io/badge/license-Apache--2.0-black)](./LICENSE)
[![](https://img.shields.io/badge/Docs-English%7C%E4%B8%AD%E6%96%87-blue?logo=markdown)](https://modelscope.github.io/memoryscope/#welcome-to-memoryscope-tutorial-hub)
[![](https://img.shields.io/badge/Docs-API_Reference-blue?logo=markdown)](https://modelscope.github.io/memoryscope/)
[![](https://img.shields.io/badge/Contribute-Welcome-green)](https://modelscope.github.io/memoryscope/tutorial/contribute.html)

----
## 📰 News

- **[2024-09-10]** We release MemoryScope v0.1.1.0 now, which is also available in [PyPI](https://pypi.org/simple/memoryscope/)!
----
## 🌟 What is MemoryScope？
MemoryScope provides LLM chatbots with powerful and flexible long-term memory capabilities, offering a framework for building such abilities. 
It can be applied to scenarios like personal assistants and emotional companions, continuously learning through long-term memory to remember users' basic information as well as various habits and preferences. 
This allows users to gradually experience a sense of "understanding" when using the LLM.

### Demo
<p align="center">
 <img src="https://github.com/user-attachments/assets/1754c814-1342-4288-a8a3-74d0b40f59a6" alt="en_demo" width="75%">
</p>

### Framework
<p align="center">
 <img src="./docs/images/framework.png" alt="Framework" width="75%">
</p>

💾 Memory Database: MemoryScope is equipped with a vector database (default is *ElasticSearch*) to store all memory fragments recorded in the system.

🔧 Worker Library: MemoryScope atomizes the capabilities of long-term memory into individual workers, including over 20 workers for tasks such as query information filtering, observation extraction, and insight updating.

🛠️ Operation Library: Based on the worker pipeline, it constructs the operations for memory services, realizing key capabilities such as memory retrieval and memory consolidation.

- Memory Retrieval: Upon arrival of a user query, this operation returns the semantically related memory pieces 
and/or those from the corresponding time if the query involves reference to time.
- Memory Consolidation: This operation takes in a batch of user queries and returns important user information
extracted from the queries as consolidated *observations* to be stored in the memory database.
- Reflection and Re-consolidation: At regular intervals, this operation performs reflection upon newly recorded *observations*
to form and update *insights*. Then, memory re-consolidation is performed to ensure contradictions and repetitions
among memory pieces are properly handled.


⚙️ Best Practices:

- Based on the core capabilities of long-term memory, MemoryScope has implemented a dialogue interface (API) with long-term memory and a command-line dialogue practice (CLI) with long-term memory.
- MemoryScope combines currently popular agent frameworks (AutoGen, AgentScope) to provide best practices.

### Main Features

⚡ Low response-time (RT) for the user:
- Backend operations (Memory Consolidation, Reflection and Re-consolidation) are decoupled from the frontend operation
 (Memory Retrieval) in the system.
- While backend operations are usually (and are recommended to be) queued or executed at regular intervals, the 
system's response time (RT) for the user depends solely on the frontend operation, which is only ~500ms.

🌲 Hierarchical and coherent memory:
- The memory pieces stored in the system are in a hierarchical structure, with *insights* being the high level information
from the aggregation of similarly-themed *observations*.
- Contradictions and repetitions among memory pieces are handled periodically to ensure coherence of memory.
- Fictitious contents from the user are filtered out to avoid hallucinations by the LLM.

⏰ Time awareness:
- The system is time sensitive when performing both Memory Retrieval and Memory Consolidation. Therefore, it can retrieve
accurate relevant information when the query involves reference to time.

----

## 💼 Supported Model API

| Backend           | Task       | Some Supported Models                                                  |
|-------------------|------------|------------------------------------------------------------------------|
| openai_backend    | Generation | gpt-4o, gpt-4o-mini, gpt-4, gpt-3.5-turbo                              |
|                   | Embedding  | text-embedding-ada-002, text-embedding-3-large, text-embedding-3-small |
| dashscope_backend | Generation | qwen-max, qwen-plus, qwen-plus, qwen2-72b-instruct                     |
|                   | Embedding  | text-embedding-v1, text-embedding-v2                                   |
|                   | Reranker   | gte-rerank                                                             |

In the future, we will support more model interfaces and local deployment of LLM and embedding services.


## 🚀 Installation
For installation, please refer to [Installation.md](docs/installation.md). 


## 🍕 Quick Start
- [Simple Usages (Quick Start)](./examples/api/simple_usages.ipynb)
- [With AutoGen](./examples/api/autogen_example.md)
- [CLI with a MemoryScope Chatbot](./examples/cli/README.md)
- [Advanced Customization](./examples/advance/custom_operator.md)

## 💡 Contribute

Contributions are always encouraged!

We highly recommend install pre-commit hooks in this repo before committing pull requests.
These hooks are small house-keeping scripts executed every time you make a git commit,
which will take care of the formatting and linting automatically.
```shell
pip install -e .
pre-commit install
```

Please refer to our [Contribution Guide](./docs/contribution.md) for more details.

## 📖 Citation

Reference to cite if you use MemoryScope in a paper:

```
@software{MemoryScope,
author = {Li Yu and 
          Tiancheng Qin and
          Qingxu Fu and
          Sen Huang and
          Xianzhe Xu and
          Zhaoyang Liu and
          Boyin Liu},
month = {09},
title = {{MemoryScope}},
url = {https://github.com/modelscope/MemoryScope},
year = {2024}
}
```
