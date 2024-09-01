.. MemoryScope documentation master file, created by
   sphinx-quickstart on Fri Jan  5 17:53:54 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

:github_url: https://github.com/modelscope/memoryscope

MemoryScope 文档
=========================

欢迎浏览MemoryScope相关文档
-------------------------------

.. image:: ./docs/images/logo_1.png
    :align: center

MemoryScope 是一个为LLM聊天机器人服务的强大且灵活的长期记忆系统。它由一个记忆数据库和三个可定制的系统操作组成，这些操作可以灵活组合，
为您的LLM聊天机器人提供强大的长期记忆服务。

💾 记忆数据库:
^^^^^^^^^^^^^

- MemoryScope 配备了一个 *ElasticSearch (ES)* 向量数据库，用于存储系统中记录的所有记忆片段。

🛠️ 系统操作:
^^^^^^^^^^^^

- 记忆检索：当用户输入对话，此操作返回语义相关的记忆片段。如果输入对话包含对时间的指涉，则同时返回相应时间中的记忆片段。
-
- 记忆巩固：此操作接收一批用户的输入对话，并从对话中提取重要的用户信息，将其作为 *observation* 形式的记忆片段存储在记忆数据库中。
-
- 反思与再巩固：每隔一段时间，此操作对新记录的 *observations* 进行反思，以形成和更新 *insight* 形式的记忆片段。然后执行记忆再巩固，
以确保记忆片段之间的矛盾和重复得到妥善处理。

.. toctree::
   :maxdepth: 2
   :caption: MemoryScope 教程

   关于MemoryScope <README.md>
   🚀 安装 <docs/installation.md>
   命令行 <examples/cli/README.md>
   简例 <examples/api/simple_usages_cn.ipynb>

.. toctree::
   :maxdepth: 6
   :caption: MemoryScope 接口

   API <docs/api.rst>

