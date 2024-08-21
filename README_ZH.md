[**English**](./README.md) | 中文

# MemoryScope

<p align="left">
  <img src="docs/images/logo_1.png" width="700px" alt="MemoryScope Logo">
</p>

为您的大语言模型聊天机器人配备强大且灵活的长期记忆系统。

----
## 新闻

- **[2024-07-26]** 我们现在发布了 MemoryScope v0.1.0.2，该版本也可以在 [PyPI](https://pypi.org/simple) 上获取！
----
## MemoryScope 是什么？

MemoryScope 是一个为LLM聊天机器人服务的强大且灵活的长期记忆系统。它由一个记忆数据库和三个可定制的系统操作组成，这些操作可以灵活组合，
为您的LLM聊天机器人提供强大的长期记忆服务。

💾 记忆数据库:
- MemoryScope 配备了一个 *ElasticSearch (ES)* 向量数据库，用于存储系统中记录的所有记忆片段。

🛠️ 系统操作:
- 记忆检索：当用户输入对话，此操作返回语义相关的记忆片段。如果输入对话包含对时间的指涉，则同时返回相应时间中的记忆片段。
- 记忆巩固：此操作接收一批用户的输入对话，并从对话中提取重要的用户信息，将其作为 *observation* 形式的记忆片段存储在记忆数据库中。
- 反思与再巩固：每隔一段时间，此操作对新记录的 *observations* 进行反思，以形成和更新 *insight* 形式的记忆片段。然后执行记忆再巩固，
以确保记忆片段之间的矛盾和重复得到妥善处理。

### 框架
<p align="left">
  <img src="docs/images/framework.png" width="700px" alt="MemoryScope Framework">
</p>

### 主要特点

⚡ 极低的用户时延（RT）:
- 系统中后端操作（记忆巩固、反思和再巩固）与前端操作（记忆检索）相互独立。
- 由于后端操作通常（并且推荐）通过队列或每隔固定间隔执行，系统的用户时延（RT）完全取决于前端操作，仅为约500毫秒。

🌲 记忆存储的层次结构和内容的连贯一致性:
- 系统中存储的记忆片段采用分层结构，通过汇总主题相似的 *observations* 生成高层次的 *insights* 信息。
- 定期处理记忆片段之间的矛盾和重复，以保证记忆内容的连贯一致性。
- 过滤掉用户输入的虚构内容，以避免LLM产生幻觉。

⏰ 时间敏感性:
- T系统在执行记忆检索和记忆巩固时具备时间敏感性，因此在输入对话包含对时间的指涉时，可以检索到准确的相关信息。

### 用法示例
- [简易用法（快速开始）](./examples/api/simple_usages_cn.ipynb)
- [在命令行与MemoryScope聊天机器人交互](./examples/cli/dash_cli_cn1.sh)
- [进阶自定义用法](./examples/api/advanced_customization_cn.ipynb)

## 🚀 安装

## 💡 代码贡献

欢迎社区的代码贡献。

我们非常推荐每一个贡献者在代码提交前，安装`pre-commit`钩子工具，
能够帮助在每一次git提交的时候，进行自动化的代码格式校验。
```shell
poetry install --with dev
pre-commit install
```



## 📖 引用

如果您在论文中有使用该项目，请添加以下引用：

```
@software{MemoryScope,
author = {},
month = {08},
title = {{MemoryScope}},
url = {https://github.com/modelscope/MemoryScope},
year = {2024}
}
```