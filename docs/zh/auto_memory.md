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

## 可选的 Session 图像

默认不开启图像。调用时即可开启，不需要修改 YAML 或重新编译 ReMe：

```bash
reme auto_memory session_id=session-a include_images=true image_mode=resource messages='[...]'
```

`messages` 使用 AgentScope 格式，处理顶层图像 `DataBlock`（`source.media_type` 以 `image/` 开头）。
支持 Base64、HTTP(S) URL 和 workspace 内的 `file://` URI；本地读取遵守 `_allowed_paths`。
Caption 需要支持视觉的模型：共用 Auto Resource 的模型选择逻辑，优先 `vision`，其次 `default`，也可通过 Step 的
`as_llm` 显式选择。字节/像素限制和格式转换复用现有图像资源处理流程。

| 设置 | 提取 memory 时的输入 | 额外持久文件 |
| --- | --- | --- |
| `include_images=false` | 原有纯文本行为，不生成 caption | 无 |
| `include_images=true image_mode=resource` | Caption、图像笔记链接、原图资源链接 | 原图和 Auto Resource 图像笔记 |
| `include_images=true image_mode=caption-only` | 只有 caption | 无 |

开启后的两种模式都只在临时消息副本中，将图像块原位替换为 AgentScope 标准 `TextBlock`，不改变其他块或调用方消息。
它们共用内置 Auto Resource caption prompt 和模型调用基建；`resource` 把笔记生成交给配置的 `auto_resource` Job。
`caption-only` 的 caption 仅在提取时存在，不单独保存。

**所有模式的源 JSONL 保存行为完全相同。** 不补充 caption、资源链接或图像 metadata，仍执行上文的过滤规则。
因此，重放已保存的 JSONL 无法恢复被过滤掉的 Base64 图像；再次处理这些图像需要重新提交原始带图消息。

`resource` 将原始字节保存到 `{resource_dir}/YYYY-MM-DD/_session_images/<sha256>.<ext>`，按 `source_resource`
复用同一天的图像笔记。同一次调用中相同字节只做一次 caption；已有的同日图像卡片直接复用，不改写正文。
`_session_images` 是同步入口管理的保留附件目录，默认 resource watcher 的启动扫描和实时监听都排除它。
手动修改或删除其中的原图不会自动重新生成或删除 caption 卡片；普通资源的 watcher 行为不变。

临时文本使用英文标签：

```text
[Image]
Image note: [[daily/2026-09-09/project-architecture.md]]
Image resource: [[resource/2026-09-09/_session_images/<sha256>.png]]
Caption (model-generated):
...
[/Image]
```

`caption-only` 不包含其中的两行链接。Memory prompt 要求 Agent 在相关事实旁引用提供的图像笔记，但这是模型生成行为，
不是确定性的结果检查或规则补写。图像处理失败会明确中止 memory 提取；已保存的 JSONL，以及后续失败前已生成的原图或卡片
仍会保留，不自动回滚。

若需持久默认值，在应用配置（或 `reme start` 对应覆盖项）中设置 `jobs.auto_memory.include_images=true` 和
`jobs.auto_memory.image_mode=resource`。调用时参数优先，无需编译。本适配针对 AgentScope 消息，不扩展 Claude Code
原始 transcript 的解析。

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
