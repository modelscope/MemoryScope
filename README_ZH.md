[**English**](./README.md) | 中文

# MemoryScope

![MemoryScope Logo](./docs/images/logo.png)

为您的大语言模型聊天机器人配备强大且灵活的长期记忆系统。

[![](https://img.shields.io/badge/python-3.10+-blue)](https://pypi.org/project/memoryscope/)
[![](https://img.shields.io/badge/pypi-v0.1.1-blue?logo=pypi)](https://pypi.org/project/memoryscope/)
[![](https://img.shields.io/badge/Docs-English%7C%E4%B8%AD%E6%96%87-blue?logo=markdown)](https://modelscope.github.io/memoryscope/#welcome-to-memoryscope-tutorial-hub)
[![](https://img.shields.io/badge/Docs-API_Reference-blue?logo=markdown)](https://modelscope.github.io/memoryscope/)
[![](https://img.shields.io/badge/license-Apache--2.0-black)](./LICENSE)
[![](https://img.shields.io/badge/Contribute-Welcome-green)](https://modelscope.github.io/memoryscope/tutorial/contribute.html)

<!-- 创空间
[![](https://img.shields.io/badge/ModelScope-Demos-4e29ff.svg?logo=data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgMjI0IDEyMS4zMyIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KCTxwYXRoIGQ9Im0wIDQ3Ljg0aDI1LjY1djI1LjY1aC0yNS42NXoiIGZpbGw9IiM2MjRhZmYiIC8+Cgk8cGF0aCBkPSJtOTkuMTQgNzMuNDloMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzYyNGFmZiIgLz4KCTxwYXRoIGQ9Im0xNzYuMDkgOTkuMTRoLTI1LjY1djIyLjE5aDQ3Ljg0di00Ny44NGgtMjIuMTl6IiBmaWxsPSIjNjI0YWZmIiAvPgoJPHBhdGggZD0ibTEyNC43OSA0Ny44NGgyNS42NXYyNS42NWgtMjUuNjV6IiBmaWxsPSIjMzZjZmQxIiAvPgoJPHBhdGggZD0ibTAgMjIuMTloMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzM2Y2ZkMSIgLz4KCTxwYXRoIGQ9Im0xOTguMjggNDcuODRoMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzYyNGFmZiIgLz4KCTxwYXRoIGQ9Im0xOTguMjggMjIuMTloMjUuNjV2MjUuNjVoLTI1LjY1eiIgZmlsbD0iIzM2Y2ZkMSIgLz4KCTxwYXRoIGQ9Im0xNTAuNDQgMHYyMi4xOWgyNS42NXYyNS42NWgyMi4xOXYtNDcuODR6IiBmaWxsPSIjNjI0YWZmIiAvPgoJPHBhdGggZD0ibTczLjQ5IDQ3Ljg0aDI1LjY1djI1LjY1aC0yNS42NXoiIGZpbGw9IiMzNmNmZDEiIC8+Cgk8cGF0aCBkPSJtNDcuODQgMjIuMTloMjUuNjV2LTIyLjE5aC00Ny44NHY0Ny44NGgyMi4xOXoiIGZpbGw9IiM2MjRhZmYiIC8+Cgk8cGF0aCBkPSJtNDcuODQgNzMuNDloLTIyLjE5djQ3Ljg0aDQ3Ljg0di0yMi4xOWgtMjUuNjV6IiBmaWxsPSIjNjI0YWZmIiAvPgo8L3N2Zz4K)](https://modelscope.cn/studios?name=memoryscope&page=1&sort=latest)
-->


----
## 新闻

- **[2024-09-06]** 我们现在发布了 MemoryScope v0.1.1，该版本也可以在 [PyPI](https://pypi.org/simple/memoryscope/) 上获取！
----

## 什么是MemoryScope？
MemoryScope可以为LLM聊天机器人提供强大且灵活的长期记忆能力，并提供了构建长期记忆能力的框架。
MemoryScope可以用于个人助理、情感陪伴等记忆场景，通过长期记忆能力来不断学习，记得用户的基础信息以及各种习惯和喜好，使得用户在使用LLM时逐渐感受到一种“默契”。

![Framework](./docs/images/framework.png)

### 核心框架：

💾 记忆数据库: MemoryScope配备了向量数据库(默认是*ElasticSearch*)，用于存储系统中记录的所有记忆片段。

🔧 核心worker库: MemoryScope将长期记忆的能力原子化，抽象成单独的worker，包括query信息过滤，observation抽取，insight更新等20+worker。

🛠️ 核心Op库: 并基于worker的pipeline构建了memory服务的核心operation，实现了记忆检索，记忆巩固等核心能力。

- 记忆检索：当用户输入对话，此操作返回语义相关的记忆片段。如果输入对话包含对时间的指涉，则同时返回相应时间中的记忆片段。
- 记忆巩固：此操作接收一批用户的输入对话，并从对话中提取重要的用户信息，将其作为 *observation* 形式的记忆片段存储在记忆数据库中。
- 反思与再巩固：每隔一段时间，此操作对新记录的 *observations* 进行反思，以形成和更新 *insight*
   形式的记忆片段。然后执行记忆再巩固，以确保记忆片段之间的矛盾和重复得到妥善处理。

⚙️ 最佳实践:

- MemoryScope在构建了长期记忆核心能力的基础上，实现了带长期记忆的对话接口(API)和带长期记忆的命令行对话实践(CLI)。
- MemoryScope结合了目前流行的Agent框架（AutoGen、AgentScope），给出了最佳实践。

### 🤝主要特点

⚡ 极低的线上时延（RT）:
- 系统中后端操作（记忆巩固、反思和再巩固）与前端操作（记忆检索）相互独立。
- 由于后端操作通常（并且推荐）通过队列或每隔固定间隔执行，系统的用户时延（RT）完全取决于前端操作，仅为约500毫秒。

🌲 记忆存储的层次结构和内容的连贯一致性:
- 系统中存储的记忆片段采用分层结构，通过汇总主题相似的 *observations* 生成高层次的 *insights* 信息。
- 定期处理记忆片段之间的矛盾和重复，以保证记忆内容的连贯一致性。
- 过滤掉用户输入的虚构内容，以避免LLM产生幻觉。

⏰ 时间敏感性:
- T系统在执行记忆检索和记忆巩固时具备时间敏感性，因此在输入对话包含对时间的指涉时，可以检索到准确的相关信息。

----

## 💼 支持的模型API

| Backend           | Task       | Some Supported Models                                                  |
|-------------------|------------|------------------------------------------------------------------------|
| openai_backend    | Generation | gpt-4o, gpt-4o-mini, gpt-4, gpt-3.5-turbo                              |
|                   | Embedding  | text-embedding-ada-002, text-embedding-3-large, text-embedding-3-small |
| dashscope_backend | Generation | qwen-max, qwen-plus, qwen-plus, qwen2-72b-instruct                     |
|                   | Embedding  | text-embedding-v1, text-embedding-v2                                   |
|                   | Reranker   | gte-rerank                                                             |

未来将支持更多的模型接口和支持本地部署的LLM和emb服务

----
## 🚀 安装

### 1. 使用 Docker 安装

### 2. 使用 Docker Compose 安装

### 3. 使用 PYPI + Docker 安装 [仅限 Linux & MacOS]

### 3. 使用 从源码安装 + Docker 安装 [仅限 Linux & MacOS]

### Docker方式一键运行Demo

<!--
运行 `sudo docker run -it --rm --net=host memoryscope/memoryscope` 一键运行memoryscope的演示。
-->

完整的安装方法请参考[安装指南](docs/installation_zh.md)。

## 快速开始
- [简易用法（快速开始）](./examples/api/simple_usages_cn.ipynb)
- [在命令行与MemoryScope聊天机器人交互](./examples/cli/README_ZH.md)
- [进阶自定义用法](./examples/advance/custom_operator.md)
- [结合AutoGen使用](./examples/api/autogen_example.md)


## 💡 代码贡献

欢迎社区的代码贡献。

我们非常推荐每一个贡献者在代码提交前，安装`pre-commit`钩子工具，
能够帮助在每一次git提交的时候，进行自动化的代码格式校验。
```shell
poetry install --with dev
pre-commit install
```

Please refer to our [Contribution Guide](./docs/contribute_zh.md) for more details.

## 📖 引用

如果您在论文中有使用该项目，请添加以下引用：

```
@software{MemoryScope,
author = {Li Yu and 
          Tiancheng Qin and
          Qingxu Fu and
          Sen Huang and
          Xianzhe Xu and
          Zhaoyang Liu},
month = {09},
title = {{MemoryScope}},
url = {https://github.com/modelscope/MemoryScope},
year = {2024}
}
```