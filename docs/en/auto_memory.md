# Auto Memory

Auto Memory is ReMe's entry point for conversational memory. Within a target date, it uses `session_id` to find or update at
most one daily memory card, whose filename is a concise topic or event name chosen by the Agent. The day's `YYYY-MM-DD.md`
page indexes those cards. It turns "we talked about it" into "it was remembered" while retaining a source conversation record
as evidence.

<p align="center">
  <img src="../figure/auto-memory-resource.svg" alt="ReMe Auto Memory and Auto Resource writing daily memory cards" width="92%">
</p>

For the general file semantics of `daily/`, `session/`, frontmatter, and wikilinks, see
[Memory as File](./memory_as_file.md).

```text
Conversation
  ├─ step 1: daily/YYYY-MM-DD/<generated_name>.md # one topic-named card per session
  ├─ step 2: daily/YYYY-MM-DD.md                  # daily index linking the cards
  └─ source: session/dialog/<session_id>.jsonl    # source conversation record
```

## What It Records

Auto Memory does not preserve a chat transcript as a running summary. It records information that may remain useful later:

- User preferences: preferred style, collaboration habits, and long-term requirements.
- Key facts: project background, important numbers, explicit conclusions, and constraints.
- Process decisions: what happened, why a choice was made, and which alternatives were rejected.
- Current state: what has been completed, what is blocked, and what comes next.
- Reusable experience: commands, workflows, diagnostic methods, and solutions.

## Image Input (Opt-in)

Auto Memory can treat AgentScope image blocks as conversation evidence. This is disabled by default so existing text-only
workflows do not pay the additional image-token cost. Enable it persistently in the job configuration:

```yaml
jobs:
  auto_memory:
    include_images: true
```

It can also be enabled or disabled for one call with `include_images=true` or `include_images=false`. When enabled, image
blocks are sent directly to the vision-capable model bound to the default AgentScope agent wrapper; Auto Memory does not
create or inject an intermediate caption. Text and images retain their order and are interpreted together with the
message's speaker and timestamp.

The input uses AgentScope `data` blocks. For example:

```json
{
  "name": "user",
  "role": "user",
  "content": [
    {"type": "text", "text": "Remember the project code shown here."},
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

The configured model must support image input, and Auto Memory performs no caption fallback. Only `image/*` data blocks
are included; audio, video, tool results, and other data are ignored. Remote images must use HTTP(S). Local `file://`
images must stay inside the ReMe workspace and, like inline Base64 images, are limited to 5 MiB each. A local file is read
by ReMe and converted to Base64 before the provider call.

With the default AgentScope wrapper, an image-enabled extraction uses an ephemeral internal agent session, so its image
payload is not written to `mem_session/agentscope`. Inline Base64 bytes are also removed from the saved source
conversation; image URLs remain there as part of the original message. If the switch is off, image blocks are completely
absent from model input—no file is read and no placeholder, synthesized caption, or fallback caption is added.

For non-empty calls, response metadata reports `include_images_requested`, the effective `include_images` value, and the
number of top-level image blocks as `image_count`. This makes image-on and image-off runs auditable without inspecting the
model prompt.

## Write Location

Auto Memory writes distilled memories to `daily/`. Conversations from the same day first become individual cards:

Example directory:

```text
workspace/
  daily/
    2026-06-20.md
    2026-06-20/
      login-refactor-decision.md
      retrieval-regression.md
```

The two files under the date directory are topic-named cards distilled from different conversations.
`daily/2026-06-20.md` is the index page for that day. Resource files enter the same daily memory layer; see
[Auto Resource](./auto_resource.md).

When a call includes `session_id`, Auto Memory uses it to find the corresponding card through frontmatter, while the Agent
chooses a readable filename through `name`:

```yaml
name: login-refactor-decision
session_id: session-a
source_conversation: "[[session/dialog/session-a.jsonl]]"
```

This keeps different conversations separate without forcing opaque IDs into filenames. An update locates the existing note by
`session_id` or `source_conversation`; if the Agent supplies a better frontmatter `name`, the system can rename the note and
retarget inbound wikilinks. To see what happened on a day, start with `YYYY-MM-DD.md`.

## Preserving the Original Information

The distilled daily note is optimized for readability; a filtered source conversation record is retained for trust and
verification.

While generating memory cards, Auto Memory also saves the source messages:

```text
session/
  dialog/
    session-a.jsonl
    session-b.jsonl
```

Each daily note points to its corresponding conversation record. Saved messages omit tool-result blocks and base64 data
blocks, preventing recalled memory and binary payloads from being mistaken for user-provided evidence later.

## Message Timestamps

Auto Memory preserves each retained message's `created_at` in both the prompt and the source conversation JSONL. When importing historical
conversations or benchmark data, provide the actual occurrence time for every message so the model does not confuse event
time with execution time:

```bash
reme auto_memory \
  session_id=locomo-session \
  messages='[
    {"role":"user","content":"Jon lost his job today.","created_at":"2023-01-19T08:00:00"},
    {"role":"assistant","content":"I am sorry to hear that.","created_at":"2023-01-19T08:01:00"}
  ]'
```

For compatibility with common dataset schemas, `auto_memory` also checks `time_created`, `timestamp`, `createdAt`,
`timeCreated`, and `created_time` when `created_at` is absent. These fields may appear either at the top level of a message
or inside `metadata`.

When a call does not explicitly provide `date`, Auto Memory uses the latest valid `created_at` date in the messages. If no
message contains a valid timestamp, it falls back to the current date. Historical imports may also specify the
target date directly:

```bash
reme auto_memory \
  session_id=locomo-session \
  date=2023-01-19 \
  messages='[{"role":"user","content":"Jon lost his job today."}]'
```

## What Happens Next

Auto Memory only creates memory in the daily layer. To distill this material further into long-term `digest/` nodes, use
[Auto Dream](./auto_dream.md). To search daily and digest content, use [Memory Search](./memory_search.md).
