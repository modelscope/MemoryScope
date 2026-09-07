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

也可以在单次调用中用 `include_images=true` 或 `include_images=false` 覆盖。开启后，Auto Memory 先用视觉模型描述图像，
生成链接原图的图像卡片，再在对话副本中用 caption 和卡片链接替换图像块。原有文本、内容块顺序、说话者和时间戳保持不变，
随后由原来的纯文本记忆 Agent 整理对话事实。

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

只处理顶层 `image/*` data block，工具结果中嵌套的图像、音频、视频及其他数据会被忽略。支持内嵌 Base64、HTTP(S) URL，
以及 workspace 内的本地 `file://` URL。workspace 外的路径及指向外部的符号链接会被拒绝。生成 caption 使用
`auto_memory_step` 选择的 `as_llm` 组件，默认名称为 `default`，该模型必须支持图像输入；记忆 Agent 保持自身的模型配置。
可以选择专门的 caption 模型：

```yaml
jobs:
  auto_memory:
    include_images: true
    steps:
      - backend: auto_memory_step
        as_llm: vision
```

该示例需要配置 `components.as_llm.vision`。支持 PNG、JPEG、WebP、GIF、BMP 和 TIFF，原文件上限为 50 MiB、4000 万像素。
动态图或多页图像只描述第一帧。发给模型的副本会纠正方向，将最长边缩小到最多 2048 像素，并控制在 5 MiB 内；保存的原图保持不变。

原图字节复制到配置的 session 目录，caption 作为 daily 卡片保存：

```text
session/images/<content-hash>.<extension>                # 原图字节
session/dialog/<session_id>.jsonl                       # 带持久本地图像引用的消息
daily/<first-caption-date>/session-image-<fingerprint>.md # caption 和原图链接
```

这些 session 附件不进入 resource watcher，Auto Memory 不会调用 `auto_resource`。图像卡片通过 `kind: session_image`
和 `source_resource` 标识原图；session 卡片继续使用既有的 `session_id` 和 `source_conversation` 字段。写入图像记忆时，
系统维护 session 卡片的 `image_notes` 链接，后续关闭图像后的更新也会保留这些链接，使 Agent 重写会话卡片后仍能追溯图像证据。

Caption 描述可见事实，以及有意义的文字、数字和日期。同一图像内容与 caption 配置可以复用已有结果。
依赖具体对话的人物身份或关系由记忆 Agent 根据周边消息关联，不写入共享的图像 caption。
复用依据卡片的 frontmatter 身份，因此重命名或移动到另一个 daily 日期后仍可复用，并重新读取当前 Markdown 正文，保留用户编辑。
同一身份存在多份卡片、原图被修改或来源链接不一致时会明确报错，不覆盖已有证据。查询元数据仅在单次调用内复用；普通新建和
重命名会触发刷新，对尚未选中卡片的身份元数据做原地修改则保证在下一次调用时发现。

Caption 仅出现在记忆提取所用的对话副本中，不写入来源对话。持久化的图像块指向本地副本，后续可以重新处理，无需调用方再次发送
Base64 字节，也不依赖远程 URL 一直有效。如果图像处理失败，调用会在运行记忆 Agent 前报告失败；已完成的图像产物可在重试时复用。
原图附件、caption 卡片和对话更新会先完整写入临时文件再发布，不覆盖已有的非本功能文件；已保存 JSONL 存在无效记录时会报错，
而不是静默丢弃。相同 session 的图像开启和关闭调用共用进程内锁，但不提供跨进程协调或多文件事务；请避免多个 ReMe 进程
同时写入同一 workspace。

`include_images=false` 使用原来的纯文本输入，不读取、描述或为图像生成文件，也不加入图像占位符或回退 caption。
开启开关但消息中没有图像块时同样走纯文本路径。关闭开关不会移除 workspace 中已有的图像事实；比较开启与关闭图像的效果时，应使用
各自独立的 workspace。

开启图像的调用在响应 metadata 中提供 `auto_memory_images`，记录图像数量和逐图处理结果，并通过 `image_note_paths` 返回写入或
复用的图像卡片路径。新卡片何时可被搜索，仍由正常的后台索引流程决定。关闭图像的调用保持既有响应结构。
图像 metadata 还通过 `source_modified`、`notes_modified` 和逐日 `indexes` 结果报告落盘情况。失败时也可能已有证据保存，
重试前可以查看这些字段和返回路径。daily 索引失败会如实报错并保留已写卡片，后续重试可重建缺失或不完整的图像卡片索引。
图像开启时，顶层 `modified` 包含来源文件、caption 卡片和索引修复的改动，不仅指 session 卡片。

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

session 记忆卡片会指向对应的对话记录。持久化时排除 tool-result block 和内嵌 Base64 数据；开启图像记忆时，原图字节单独保存，
图像块保留为本地文件引用。Caption 留在图像卡片和临时提取输入中，使生成的描述与来源对话保持区分。

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
