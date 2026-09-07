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

It can also be enabled or disabled for one call with `include_images=true` or `include_images=false`. When enabled, Auto
Memory first describes each image with a vision model and creates a source-linked image card. It replaces the image block
with its caption and card link in a copy of the conversation, preserving the original text, block order, speakers, and
timestamps. The existing text-only memory agent then records the conversation facts.

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

Only top-level `image/*` data blocks are processed. Images nested in tool results, audio, video, and other data are ignored.
Supported image sources are inline Base64, HTTP(S) URLs, and local `file://` URLs inside the workspace. Local paths outside
the workspace, including symlinks escaping it, are rejected. The caption model is the `as_llm` component selected by
`auto_memory_step` (`default` unless overridden) and must support image input. The memory agent keeps its own configured
model. To select a dedicated caption model:

```yaml
jobs:
  auto_memory:
    include_images: true
    steps:
      - backend: auto_memory_step
        as_llm: vision
```

This example requires a configured `components.as_llm.vision` model. Supported image formats are PNG, JPEG, WebP, GIF,
BMP, and TIFF. The source limit is 50 MiB and 40 million pixels. Only the first frame of animated or multi-page images is
captioned. The provider copy is orientation-corrected, reduced to at most 2048 pixels on its longest side, and limited to
5 MiB; the saved original remains unchanged.

The original image bytes are copied into the configured session directory, and the caption is stored as a daily card:

```text
session/images/<content-hash>.<extension>                # original image bytes
session/dialog/<session_id>.jsonl                       # messages with durable local image references
daily/<first-caption-date>/session-image-<fingerprint>.md # caption and original-image link
```

These session attachments are separate from the resource watcher. Auto Memory does not invoke `auto_resource`. Image
cards use `kind: session_image` and `source_resource` to identify their original images; session cards retain their existing
`session_id` and `source_conversation` fields. A session card's `image_notes` links are maintained even during later
image-disabled updates, so the image evidence remains reachable when the agent rewrites the session card.

Captions describe visible facts and meaningful text, numbers, and dates. They are reused for the same image content and
caption configuration. Conversation-specific identities and relationships
are interpreted by the memory agent from the surrounding messages, rather than being added to a shared image caption.
Reuse follows the card's frontmatter identity, including after a rename or move to another daily date. Its current Markdown
body is read again, so user edits remain authoritative. Conflicting owners, a changed original, or inconsistent source links
fail explicitly without overwriting the evidence. Lookup metadata is scoped to one invocation; ordinary creates and renames
refresh it, while in-place identity edits to unselected cards are guaranteed to be discovered on the next invocation.

Caption text appears only in the memory-extraction copy, never in the saved source conversation. The saved image block
points to the local copy, allowing it to be processed again without the caller resending Base64 bytes or a remote URL
remaining available. If image processing fails, the call reports the failure before invoking the memory agent; completed
image artifacts can be reused on retry.
Original attachments, caption cards, and conversation updates are staged and published as complete files. Existing
unowned files are not overwritten; invalid saved JSONL is reported rather than silently discarded. Image-enabled and
image-disabled calls for the same session share an in-process lock. This does not coordinate separate ReMe processes or
provide an all-files transaction; avoid concurrent writers from separate processes to the same workspace.

With `include_images=false`, Auto Memory uses its original text-only input and does not read, caption, or create artifacts
for images. It adds no image placeholder or fallback caption. Enabling the switch on a conversation with no image blocks
also uses the text-only path. Turning the switch off does not remove image facts already stored in the workspace; use
separate workspaces when comparing image-on and image-off runs.

Image-enabled calls include `auto_memory_images` response metadata, with the image count and per-image processing results,
plus `image_note_paths`. These paths report written or reused image cards; normal background indexing still determines when
new cards become searchable. Image-disabled calls keep the existing response shape.
The image metadata also reports `source_modified`, `notes_modified`, and per-day `indexes` results. A failed call may still
have saved evidence: use these fields and the reported paths before retrying. Daily-index errors report failure while
preserving already written cards; a later retry can rebuild a missing or incomplete image-card index. For image-enabled
calls, top-level `modified` includes saved sources, caption cards, and index repairs, not only the session card.

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

Each session memory note points to its corresponding conversation record. Saved messages omit tool-result blocks and
inline Base64 data. With image memory enabled, image bytes are saved separately and their blocks are retained as local
file references. Captions remain in image cards and in the temporary extraction input, keeping generated descriptions
separate from the source conversation.

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
