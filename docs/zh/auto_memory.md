# Auto Memory

Auto Memory 是 ReMe 的对话记忆入口：在目标日期内，它用 `session_id` 定位或更新最多一张 daily 记忆卡片，文件名由 Agent
根据内容生成简洁的主题或事件名，再由当天的 `YYYY-MM-DD.md` 统一索引。它负责把“聊过”变成“记住”，并保留可追溯的对话记录。

<p align="center">
  <img src="../figure/auto-memory-resource.svg" alt="ReMe Auto Memory 与 Auto Resource 写入 daily 记忆卡片的流程" width="92%">
</p>

关于 `daily/`、`session/`、frontmatter 和 wikilink 的通用文件语义，见 [Memory as File](./memory_as_file.md)。

```text
Conversation
  ├─ step 1: daily/YYYY-MM-DD/<generated_name>.md # 每个 session 一张主题卡片
  ├─ step 2: daily/YYYY-MM-DD.md                  # 当天索引再串起来
  └─ source: session/dialog/<session_id>.jsonl    # 对话来源记录
```

## 它记录什么

它不记录聊天流水账，只记录以后可能还会用到的内容：

- 用户偏好：喜欢什么风格、习惯怎么协作、长期要求是什么。
- 关键事实：项目背景、重要数字、明确结论、限制条件。
- 过程决定：发生了什么，为什么这么选，哪些方案被放弃。
- 当前状态：做到哪一步，卡在哪里，下一步是什么。
- 可复用经验：命令、流程、排查方法、解决方案。

## 图像输入（可选）

Auto Memory 可以把 AgentScope 图像块作为对话证据。该功能默认关闭，使现有纯文本流程不会产生额外的读图 token
开销。可以在 Job 配置中长期启用：

```yaml
jobs:
  auto_memory:
    include_images: true
```

也可以在单次调用中用 `include_images=true` 或 `include_images=false` 覆盖。开启后，图像块会直接发送给默认
AgentScope Agent Wrapper 所绑定的多模态模型；Auto Memory 不会生成或注入中间 caption。文本和图像保持原始顺序，
并与消息的说话者和时间戳一起解释。

输入使用 AgentScope `data` block，例如：

```json
{
  "name": "user",
  "role": "user",
  "content": [
    {"type": "text", "text": "记住这张图里显示的项目代码。"},
    {
      "type": "data",
      "name": "project-board",
      "source": {
        "type": "url",
        "url": "https://example.com/project-board.png",
        "media_type": "image/png"
      }
    }
  ]
}
```

配置的模型必须支持图像输入，Auto Memory 不执行 caption fallback。只有 `image/*` data block 会进入模型，
音频、视频、工具结果及其他数据会被忽略。远程图像必须使用 HTTP(S)。本地 `file://` 图像必须位于 ReMe
workspace 内，且与内嵌 Base64 图像一样，每张不得超过 5 MiB。ReMe 会先读取本地文件并转换为 Base64，再调用模型。

使用默认 AgentScope wrapper 时，开启图像的提取会使用临时的内部 agent session，因此图像 payload 不会写入
`mem_session/agentscope`。内嵌 Base64 字节也会从保存的来源对话中移除；图像 URL 作为原始消息的一部分会被保留。
开关关闭时，模型输入中完全没有图像块，不会读取图像文件，也不会自动加入占位符、生成的 caption 或回退 caption。

对于非空调用，响应 metadata 会记录 `include_images_requested`、实际生效的 `include_images` 以及顶层图像块数量
`image_count`，便于在不检查模型 prompt 的情况下审计开启与关闭图像的运行。

## 写入位置

Auto Memory 会把整理后的记忆放进 `daily/`。当天发生的对话会先被整理成一张张小卡片：

示例目录：

```text
workspace/
  daily/
    2026-06-20.md
    2026-06-20/
      login-refactor-decision.md
      retrieval-regression.md
```

日期目录下的两个文件是不同对话整理出的主题卡片，`daily/2026-06-20.md` 是当天索引页。资源文件也会进入
同一个 daily 记忆层，见 [Auto Resource](./auto_resource.md)。

当调用时带上 `session_id`，Auto Memory 会通过 frontmatter 用它定位卡片，Agent 则通过 `name` 决定可读文件名：

```yaml
name: login-refactor-decision
session_id: session-a
source_conversation: "[[session/dialog/session-a.jsonl]]"
```

这样既能分开不同对话，又不必把不透明的 ID 当文件名。更新时会按 `session_id` 或 `source_conversation` 找到旧卡片；如果 Agent
提供了更好的 frontmatter `name`，系统可重命名并重定向入链。查看某天内容时从 `YYYY-MM-DD.md` 开始。

## 同时保存原始信息

整理后的 daily note 负责“好读”，过滤后的对话来源记录负责“可信”。

Auto Memory 在生成记忆卡片的同时，也会保存对话来源消息：

```text
session/
  dialog/
    session-a.jsonl
    session-b.jsonl
```

daily note 会指向对应的对话记录。持久化时会排除 tool-result block 和 base64 data block，避免召回记忆或二进制负载在后续流程中被误当成
用户提供的证据。

## 消息时间

Auto Memory 会在 prompt 和对话来源 JSONL 中保留每条已保留消息的 `created_at`。导入历史对话或 benchmark 数据时，建议为每条
message 提供真实发生时间，避免模型把事件时间误解为运行时间：

```bash
reme auto_memory \
  session_id=locomo-session \
  messages='[
    {"role":"user","content":"Jon lost his job today.","created_at":"2023-01-19T08:00:00"},
    {"role":"assistant","content":"I am sorry to hear that.","created_at":"2023-01-19T08:01:00"}
  ]'
```

为了兼容常见数据集字段，`auto_memory` 也会在缺少 `created_at` 时读取 `time_created`、`timestamp`、`createdAt`、
`timeCreated` 或 `created_time`。这些字段可以放在 message 顶层，也可以放在 `metadata` 中。

当调用没有显式传入 `date` 时，Auto Memory 会使用消息中最晚的有效 `created_at` 日期作为 daily note 日期；如果消息没有有效时间，
则回退到当前日期。历史导入也可以显式指定目标日期：

```bash
reme auto_memory \
  session_id=locomo-session \
  date=2023-01-19 \
  messages='[{"role":"user","content":"Jon lost his job today."}]'
```

## 后续流向

Auto Memory 只生成 daily 层记忆。要把这些材料进一步沉淀为长期 `digest/` 节点，使用 [Auto Dream](./auto_dream.md)；要搜索
daily 和 digest，使用 [Memory Search](./memory_search.md)。
