.. MemoryScope documentation master file, created by
   sphinx-quickstart on Fri Jan  5 17:53:54 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

:github_url: https://github.com/modelscope/memoryscope

MemoryScope Documentation
=========================

Welcome to MemoryScope Tutorial
-------------------------------

.. image:: docs/images/logo_1.png
    :align: center

MemoryScope is a powerful and flexible long term memory system for LLM chatbots. It consists
of a memory database and three customizable system operations, which can be flexibly combined to provide
robust long term memory services for your LLM chatbot.

💾 Memory Database:
^^^^^^^^^^^^^^^^^^^^

- MemoryScope comes with an *ElasticSearch (ES)* vector database to store all the
memory pieces recorded in the system.

🛠️ System operations:
^^^^^^^^^^^^^^^^^^^^^

- Memory Retrieval: Upon arrival of a user query, this operation returns the semantically related memory pieces
and/or those from the corresponding time if the query involves reference to time.

- Memory Consolidation: This operation takes in a batch of user queries and returns important user information
extracted from the queries as consolidated *observations* to be stored in the memory database.

- Reflection and Re-consolidation: At regular intervals, this operation performs reflection upon newly recorded *observations*
to form and update *insights*. Then, memory re-consolidation is performed to ensure contradictions and repetitions
among memory pieces are properly handled.

.. toctree::
   :maxdepth: 2
   :caption: MemoryScope Tutorial

   About MemoryScope <README.md>
   🚀 Installation <docs/installation.md>
   Cli Client <examples/cli/README.md>
   Simple Usages <examples/api/simple_usages_en.ipynb>

.. toctree::
   :maxdepth: 6
   :caption: MemoryScope API Reference

   API <docs/api.rst>
