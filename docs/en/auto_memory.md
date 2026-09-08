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

## Optional Session Images

Images are disabled by default. Enable them per call without editing YAML or rebuilding ReMe:

```bash
reme auto_memory session_id=session-a include_images=true image_mode=resource messages='[...]'
```

Pass AgentScope messages in `messages`, with top-level `DataBlock` images (`source.media_type` starting with `image/`).
Sources may be Base64, HTTP(S) URLs, or `file://` URIs inside the workspace. Local reads respect `_allowed_paths`.
Captioning requires a vision-capable model; the shared Auto Resource resolver prefers `vision`, then `default`, unless
the Step explicitly selects `as_llm`. Byte/pixel limits and format conversion use the existing image-resource pipeline.

| Setting | Memory extraction input | Extra durable files |
| --- | --- | --- |
| `include_images=false` | Existing text-only behavior; no image captioning | None |
| `include_images=true image_mode=resource` | Caption plus image-note and original-resource wikilinks | Original image and Auto Resource image note |
| `include_images=true image_mode=caption-only` | Caption only | None |

Both enabled modes replace each image block with a standard AgentScope `TextBlock` in a temporary message copy, at the
same position. Non-image blocks and caller-owned messages are unchanged. Both use the built-in Auto Resource caption
prompt and shared model-call infrastructure; `resource` delegates note creation to the configured `auto_resource` job.
In `caption-only`, the caption exists only during extraction, not as a separate stored caption.

**Source JSONL saving is identical in all modes.** No captions, resource links, or image metadata are added to it, and
the existing filtering above still applies. In particular, replaying a saved JSONL cannot recover omitted Base64 images;
resubmit the original image-bearing messages to process those images again.

`resource` stores original bytes under `{resource_dir}/YYYY-MM-DD/_session_images/<sha256>.<ext>` and reuses same-day
image notes by `source_resource`. Identical bytes are captioned once per call; same-day existing cards are reused without
overwriting their content. The reserved `_session_images` attachments are processed synchronously, and the default resource
watcher excludes them from both startup and live scans. Manual edits/deletions in that directory do not automatically
regenerate or delete caption cards. Ordinary resource files retain their existing watcher behavior.

The temporary text uses English labels:

```text
[Image]
Image note: [[daily/2026-09-09/project-architecture.md]]
Image resource: [[resource/2026-09-09/_session_images/<sha256>.png]]
Caption (model-generated):
...
[/Image]
```

`caption-only` omits the two link lines. The memory prompt asks the Agent to cite supplied image notes beside relevant
facts; this is model-driven, not a guaranteed post-processing repair. Image failures stop memory extraction explicitly;
the already-saved JSONL and any resources/cards created before a later failure remain available, with no rollback.

For a persistent default, set `jobs.auto_memory.include_images=true` and `jobs.auto_memory.image_mode=resource` in the
application configuration (or the corresponding `reme start` overrides). Call-time options take precedence. No compilation
is needed. This adapter targets AgentScope messages, not Claude Code transcript parsing.

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
