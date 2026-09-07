# Proactive

`proactive_read` 是 ReMe 的主动记忆读取接口。它不重新分析 daily，也不调用 LLM，只读取独立 proactive refresh
流程写出的兴趣主题：

```text
daily/<date>/interests.yaml
```

上层 Agent 可以用它获取“今天值得主动关注什么”，再决定是否提醒、追问、推荐下一步或生成主动洞察。

`interests.yaml` 由 `proactive_refresh_cron` 生成；`proactive_read` 只负责读取和暴露结果。Auto Dream 是独立的
daily-to-digest 流程，不读取或写入 proactive 状态。

## 配置入口

默认配置在 `reme/config/default.yaml`：

```yaml
proactive_read:
  backend: base
  description: "Proactive: read daily/<date>/interests.yaml and expose the latest user-interest topics."
  parameters:
    type: object
    properties:
      date:
        type: string
        default: ""
      include_content:
        type: boolean
        default: true
      horizon_days:
        type: integer
        default: 1
      min_confidence:
        type: number
        default: 0.4
  steps:
    - backend: proactive_step
      min_confidence: 0.4
```

参数含义：

| 参数              | 作用                                                                        |
|-------------------|-----------------------------------------------------------------------------|
| `date`            | 要读取的日期，格式为 `YYYY-MM-DD`。为空时使用应用时区中的今天。              |
| `include_content` | 是否在 answer 和 metadata 中返回 YAML 原文，默认 `true`。                    |
| `horizon_days`    | 读取单日曝光文件，或在更宽时间窗下读取 truth source；默认 `1`。              |
| `min_confidence`  | 返回 topic 的最低置信度，默认 `0.4`；旧版 topic 使用 `0.5`。                 |

## 输入契约

当前 proactive refresh 生成的文件如下：

```yaml
version: 2
date: 2026-06-20
generated_at: 2026-06-20T18:00:00+08:00
push: true
topics:
  - id: b2120f3573cb
    title: 记忆检索链路的质量回归
    reason: 用户近期持续修改 search、node_search 和 dream 集成链路。
    kind: follow_up
    confidence: 0.86
    first_seen: 2026-06-20
    last_evidence_at: 2026-06-20
    evidence: daily/2026-06-20/session.md
    paths:
      - daily/2026-06-20/session.md
agenda:
  - topic_id: b2120f3573cb
    title: 记忆检索链路的质量回归
    scenario_type: resume_task
    opener: 下次发布前先回顾最近的检索回归。
    next_action: 对比失败查询与上一个索引快照。
    preconditions: []
    delivery: in_conversation
    linked_memory: []
    order_reason: 证据较新且下一步明确。
suppressed: []
```

当前 v2 topic 包含稳定 ID、类型、置信度、证据日期和来源路径。读取器仍兼容包含 `title`、`reason`、`evidence`、
`keywords`、`paths` 的 v1 文件；缺少 v2 置信度时按 `0.5` 处理。

## 返回结果

成功读取时，`proactive_step` 会在主要 answer 中返回 `summary` 和 `topics`；当 `include_content=true` 时还会返回
`content`。相同的结果字段也会保留在标准 response metadata 中：

| 字段      | 说明                                            |
|-----------|-------------------------------------------------|
| `date`    | 实际读取的日期。                                |
| `path`    | `daily/<date>/interests.yaml`。                 |
| `topics`  | 解析后的 topic 列表。                           |
| `content` | YAML 原文；仅在 `include_content=true` 时返回。 |
| `skipped` | 文件不存在时为 `true`。                         |
| `error`   | 读取或解析异常。                                |
| `summary` | 简短摘要。                                      |
| `agenda`  | 当日主动议程（可选，仅 v2 文件携带时返回）。    |

当当天的 `interests.yaml` 由 proactive refresh 链路生成并携带议程时，answer 会附带
`agenda` 字段：按顺序排列的当日议程条目，每条包含 `topic_id`、`title`、`scenario_type`、
`opener`（自然口吻的开场白）、`next_action`（最小可执行动作）、`preconditions`、
`delivery`、`linked_memory` 与 `order_reason`。读侧会过滤已解决或低于 `min_confidence`
的主题对应的议程条目；文件不含议程时该字段不出现。

文件存在且解析成功时，answer 是结构化数据，例如：

```json
{
  "summary": "Read 1 proactive topic(s) from daily/2026-06-20/interests.yaml",
  "topics": [
    {
      "id": "b2120f3573cb",
      "title": "记忆检索链路的质量回归",
      "reason": "用户最近反复修改了 search、node_search 和 dream integration。",
      "kind": "follow_up",
      "confidence": 0.86,
      "first_seen": "2026-06-20",
      "last_evidence_at": "2026-06-20",
      "evidence": "daily/2026-06-20/session.md",
      "paths": ["daily/2026-06-20/session.md"]
    }
  ],
  "agenda": [
    {
      "topic_id": "b2120f3573cb",
      "title": "记忆检索链路的质量回归",
      "scenario_type": "resume_task",
      "opener": "下次发布前先回顾最近的检索回归。",
      "next_action": "对比失败查询与上一个索引快照。",
      "preconditions": [],
      "delivery": "in_conversation",
      "linked_memory": [],
      "order_reason": "证据较新且下一步明确。"
    }
  ],
  "content": "date: 2026-06-20\n..."
}
```

当 `include_content=false` 时，answer 不包含 `content` 字段。文件缺失和读取失败仍分别返回明确的
`Skipped: ...` 和 `Error: ...` 消息。

文件不存在时不会报错，而是成功返回 skipped：

```text
Skipped: interests file not found at daily/2026-06-20/interests.yaml
```

这让上层 Agent 可以把“今天还没有 proactive refresh 结果”当作正常空状态处理。

## 运行方式

CLI：

```bash
reme proactive_read date=2026-06-20
```

不返回 YAML 原文：

```bash
reme proactive_read date=2026-06-20 include_content=false
```

## 与 auto_dream 的关系

Proactive refresh 和 Auto Dream 各自独立消费 daily notes：

```text
daily notes -> auto_dream -> digest
daily notes -> proactive_refresh_cron -> daily/<date>/interests.yaml -> proactive_read -> upper-level agent
```

Proactive 职责边界如下：

| 模块                     | 职责                                         |
|--------------------------|----------------------------------------------|
| `proactive_refresh_cron` | `interests.yaml` 的唯一写入方（白天曝光）。  |
| `proactive_step`         | 读取 `interests.yaml`，暴露给上层 Agent。    |

`proactive_read` 不修改任何文件，不更新 catalog，也不负责判断是否应该主动打扰用户。它只提供当天主题材料；是否推送、何时推送、用什么语气推送，应由调用方根据产品策略决定。

## 失败模式

| 场景                       | 行为                                          |
|----------------------------|-----------------------------------------------|
| `interests.yaml` 不存在    | `success=true`，`skipped=true`，`topics=[]`。 |
| YAML 无法读取或解析异常    | `success=false`，answer 返回错误摘要。        |
| YAML 存在但没有合法 topics | `success=true`，`topics=[]`。                 |

因此推荐调用方先检查 `success`，再检查 `skipped`，最后检查 `topics` 是否为空。
