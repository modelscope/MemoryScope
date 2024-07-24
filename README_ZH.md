[**English**](./README.md) | 中文

# ModelScope

## 概念解释

- service: 在顶层的交互对象，用于定义operation的使用范围

- operation: 读写记忆等，对于记忆的操作方法，是worker的有序组合（workflow）

- workflow: 在operation中组合worker的方式

- worker: 框架中的基本工作模块

   
# 💡 代码贡献

欢迎社区的代码贡献。

我们非常推荐每一个贡献者在代码提交前，安装`pre-commit`钩子工具，
能够帮助在每一次git提交的时候，进行自动化的代码格式校验。
```shell
poetry install --with dev
pre-commit install
```



# 📖 引用

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