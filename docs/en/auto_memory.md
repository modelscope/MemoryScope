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
reme auto_memory session_id=session-a include_images=true messages='[...]'
```

For a one-shot CLI invocation, use `reme start job=auto_memory` with the same arguments.
`include_images=false` keeps the existing text-only behavior and makes no image-captioning calls. When enabled,
`image_mode` defaults to `caption-only`, the only currently supported value. `resource` mode is deferred; explicitly
selecting it or another unsupported mode while images are enabled is a configuration error, not a text fallback.

Pass AgentScope messages in `messages`, with top-level `DataBlock` images (`source.media_type` starting with `image/`).
Sources may be Base64, HTTP(S) URLs, or `file://` URIs inside the workspace. Local reads respect `_allowed_paths`.
Captioning requires a vision-capable model; the shared Auto Resource resolver prefers `vision`, then `default`, unless
the Step explicitly selects `as_llm`. Image preprocessing, model calls, and the caption prompt are shared with
`auto_image_resource`; Auto Memory does not run the `auto_resource` job or depend on its watcher.

Each caption replaces its image block with a standard AgentScope `TextBlock` in a temporary message copy, at the same
position. Non-image blocks and caller-owned messages are unchanged. The temporary text uses English labels:

```text
[Image]
Caption (model-generated):
...
[/Image]
```

Auto Memory then extracts memory from the caption-enriched copy. It saves no original-image files or separate caption
cards, and supplies no image-resource links. Relevant image facts may still become part of the normal daily memory note.

**Source JSONL saving is unchanged whether images are enabled or disabled.** No captions, resource links, or image
metadata are added to it; the existing filtering above still applies. Replaying a saved JSONL cannot recover omitted
Base64 images. Resubmit the original image-bearing messages to process those images again.

If image loading, preprocessing, or captioning fails, Auto Memory logs a warning and records the fallback in
`auto_memory_images` response metadata. It discards all temporary captions for that request and continues with the
original text-only memory input, not a partially enriched conversation. The CLI can still succeed when that normal
memory operation succeeds; inspect the metadata to distinguish text fallback from successful image processing.
Cancellation, invalid enabled image-mode configuration, and failures outside the image stage are not swallowed by this
fallback.

For a persistent default, set `jobs.auto_memory.include_images=true` in the application configuration (or the corresponding
`reme start` override). Call-time options take precedence. No compilation is needed. This adapter targets AgentScope
messages, not Claude Code transcript parsing.

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
