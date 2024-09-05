# 贡献到MemoryScope
我们的社区因其成员的多样化思想和贡献而兴旺发展。无论是修复一个错误，添加一个新功能，改进文档，还是添加示例，我们都欢迎您的帮助。以下是您做出贡献的方法：
## 报告错误和提出新功能
当您发现一个错误或者有一个功能请求，请首先检查问题跟踪器，查看它是否已经被报告。如果没有，随时可以开设一个新的问题。请包含尽可能多的细节:
- 简明扼要的标题
- 清晰地描述问题
- 提供重现问题的步骤
- 提供所使用的MemoryScope版本
- 提供所有相关代码片段或错误信息
## 对代码库做出贡献
### Fork和Clone仓库
要处理一个问题或新功能，首先要Fork仓库，然后将你的Fork克隆到本地。
```bash
git clone git@github.com:modelscope/MemoryScope.git
cd MemoryScope
```
### 创建一个新分支
为您的工作创建一个新分支。这有助于保持拟议更改的组织性，并与`main`分支分离。
```bash
git checkout -b your-feature-branch-name
```
### 做出修改
我们非常推荐每一个贡献者在代码提交前，安装`pre-commit`钩子工具，
能够帮助在每一次git提交的时候，进行自动化的代码格式校验。
```bash
# 安装开发者版本
pip install -e .
# 安装 pre-commit 钩子
pre-commit install
```

### 提交您的修改

修改完成之后就是提交它们的时候了。请提供清晰而简洁的提交信息，以解释您的修改内容。

```bash
git add -A
git commit -m "修改内容的简要描述"
```

运行时您可能会收到 `pre-commit` 给出的错误信息。请根据错误信息修改您的代码然后再次提交。

### 提交 Pull Request

当您准备好您的修改分支后，向MemoryScope的 `main` 分支提交一个Pull Request。在您的Pull Request描述中，解释您所做的修改以及其他相关的信息。

我们将审查您的Pull Request。这个过程可能涉及一些讨论以及额外的代码修改。

### 代码审查

等待我们审核您的Pull Request。我们可能会提供一些更改或改进建议。请留意您的GitHub通知，并对反馈做出响应。