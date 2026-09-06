"""Behavioral coverage for source-linked session image memory without model calls."""

# pylint: disable=protected-access

import asyncio
import base64
import hashlib
import struct
import zlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote, urlparse

from agentscope.message import Msg
from agentscope.model import ChatModelBase
import frontmatter
import httpx
import pytest

from reme.components import ApplicationContext
from reme.components.agent_wrapper import BaseAgentWrapper
from reme.components.file_store import BaseFileStore
from reme.config.config_parser import _load_config
from reme.steps.evolve import _session_images
from reme.steps.evolve._evolve import format_history
from reme.steps.evolve._image_caption import ImageCaption
from reme.steps.evolve.auto_memory import AutoMemoryStep
from reme.steps.file_io.daily_list import DailyListStep
from reme.steps.file_io.frontmatter_update import FrontmatterUpdateStep
from reme.steps.file_io.move import MoveStep
from reme.steps.file_io.write import WriteStep

_DAY = "2026-01-02"
_CAPTION = "A blue project board shows project code ORBIT-42 and a due date of 15 January."


def _png(red: int = 0) -> bytes:
    """Create a tiny valid PNG using only the standard library."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes((0, red, 0, 255))))
        + chunk(b"IEND", b"")
    )


def _text(value: str) -> dict:
    return {"type": "text", "text": value}


def _image(data: bytes | None = None) -> dict:
    return {
        "type": "data",
        "name": "project-board",
        "source": {
            "type": "base64",
            "data": base64.b64encode(_png() if data is None else data).decode("ascii"),
            "media_type": "image/png",
        },
    }


def _url(url: str, media_type: str = "image/png") -> dict:
    return {
        "type": "data",
        "source": {"type": "url", "url": url, "media_type": media_type},
    }


def _message(*content: dict, msg_id: str = "m1", **kwargs) -> Msg:
    return Msg.model_validate(
        {
            "id": msg_id,
            "name": "Sam",
            "role": "user",
            "created_at": f"{_DAY}T03:04:05Z",
            "content": list(content),
            **kwargs,
        },
    )


class _StepJob:
    """Exercise actual file steps while leaving application background jobs out."""

    def __init__(self, step_cls, app_context, file_store):
        self.step_cls = step_cls
        self.app_context = app_context
        self.file_store = file_store

    async def __call__(self, **kwargs):
        step = self.step_cls(app_context=self.app_context, file_store=self.file_store)
        result = await step(**kwargs)
        return result or step.context.response


class _RecordingAgent(BaseAgentWrapper):
    """A text-only agent boundary that optionally writes a deterministic session card."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.on_reply = None

    async def reply(self, inputs, **kwargs) -> dict:
        """Record input and perform the test's optional file write."""
        self.calls.append((inputs, kwargs))
        if self.on_reply is not None:
            await self.on_reply()
        return {"result": "Recorded session facts."}


class _Harness:
    """A temporary workspace with real note writes and mocked model boundaries."""

    def __init__(
        self,
        path: Path,
        *,
        include_images: bool = False,
        session_dir: str = "session",
    ):
        path.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.app = ApplicationContext(
            workspace_dir=str(path),
            session_dir=session_dir,
            timezone="UTC",
            language="en",
        )
        self.store = MagicMock(spec=BaseFileStore)
        self.store.workspace_path = path
        self.agent = _RecordingAgent()
        self.model = MagicMock(spec=ChatModelBase)
        self.model.model_name = "test-vision"
        self.app.jobs = {
            name: _StepJob(step_cls, self.app, self.store)
            for name, step_cls in {
                "daily_list": DailyListStep,
                "frontmatter_update": FrontmatterUpdateStep,
                "move": MoveStep,
                "write": WriteStep,
            }.items()
        }
        self.step = AutoMemoryStep(
            app_context=self.app,
            file_store=self.store,
            agent_wrapper=self.agent,
            as_llm=self.model,
            include_images=include_images,
        )

    async def run(self, messages: list[Msg], *, session_id: str = "s1", **kwargs):
        """Invoke one extraction and return its final response."""
        result = await self.step(messages=messages, session_id=session_id, **kwargs)
        return result or self.step.context.response

    def saved(self, session_id: str = "s1") -> list[Msg]:
        """Read persisted source messages without using the caller's input."""
        path = self.path / self.app.app_config.session_dir / "dialog" / f"{session_id}.jsonl"
        return [Msg.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def write_session_card_on_reply(self, session_id: str = "s1", day: str = _DAY):
        """Simulate a complete agent write to the selected session card."""

        async def write_card():
            # A complete agent write deliberately omits previous image_notes.
            # AutoMemory owns preserving those source links after the reply.
            await self.app.jobs["write"](
                path=f"daily/{day}/memory.md",
                name="memory",
                description="Session facts",
                content="Session facts.",
                metadata={
                    "session_id": session_id,
                    "source_conversation": f"[[{self.app.app_config.session_dir}/dialog/{session_id}.jsonl]]",
                },
            )

        self.agent.on_reply = write_card


@pytest.fixture(name="caption_mock")
def mock_caption(monkeypatch):
    """Replace only the visual model boundary with a deterministic caption."""
    caption = AsyncMock(
        return_value=ImageCaption(
            name="project-board",
            description="Project board ORBIT-42",
            caption=_CAPTION,
        ),
    )
    monkeypatch.setattr(_session_images, "caption_image", caption)
    return caption


@pytest.mark.asyncio
@pytest.mark.parametrize("call_kwargs", [{}, {"include_images": False}])
async def test_off_preserves_original_text_prompt_and_has_no_image_side_effects(
    tmp_path,
    caption_mock,
    call_kwargs,
):
    """Even unusable image data must not change a text-only extraction."""
    harness = _Harness(tmp_path)
    invalid_image = _image()
    invalid_image["source"]["data"] = "not-base64!"
    messages = [
        _message(
            _text("Remember the current project."),
            invalid_image,
            _text("Deadline is Friday."),
        ),
    ]
    before = messages[0].model_dump()

    response = await harness.run(messages, **call_kwargs)

    assert response.success
    inputs, options = harness.agent.calls[0]
    expected = harness.step.prompt_format(
        "user_message_create",
        today=_DAY,
        note="(none)",
        note_path="",
        session_id="s1",
        session_file="session/dialog/s1.jsonl",
        history=format_history(messages),
    )
    assert inputs == expected
    assert options["system_prompt"] == harness.step.prompt_format("system_prompt")
    assert "ephemeral" not in options
    caption_mock.assert_not_awaited()
    assert messages[0].model_dump() == before
    assert [block.type for block in harness.saved()[0].content] == ["text", "text"]
    assert not (tmp_path / "session" / "images").exists()
    assert not (tmp_path / "daily").exists()


@pytest.mark.asyncio
async def test_enabled_text_only_call_never_resolves_vision_model(
    tmp_path,
    caption_mock,
):
    """An enabled job with no images still works without a vision component."""
    harness = _Harness(tmp_path, include_images=True)
    harness.step.kwargs.pop("as_llm")

    response = await harness.run([_message(_text("A text-only memory."))])

    assert response.success
    assert isinstance(harness.agent.calls[0][0], str)
    caption_mock.assert_not_awaited()
    assert not (tmp_path / "session" / "images").exists()


@pytest.mark.asyncio
async def test_on_persists_source_and_injects_caption_in_original_block_order(
    tmp_path,
    caption_mock,
):
    """The text agent receives captions; the transcript retains images rather than captions."""
    harness = _Harness(tmp_path)
    messages = [
        _message(
            _text("Before the board."),
            _image(),
            _text("After the board."),
            metadata={"external_id": "original"},
        ),
        _message(_text("Confirmed."), msg_id="m2", name="Riley", role="assistant"),
    ]
    original = [msg.model_dump() for msg in messages]

    response = await harness.run(messages, include_images=True)

    assert response.success
    assert [msg.model_dump() for msg in messages] == original
    inputs, options = harness.agent.calls[0]
    assert isinstance(inputs, str)
    assert inputs.index("Before the board.") < inputs.index(_CAPTION) < inputs.index("After the board.")
    assert inputs.index("After the board.") < inputs.index("[Riley @") < inputs.index("Confirmed.")
    assert "[Sam @ 2026-01-02T03:04:05Z]" in inputs
    assert base64.b64encode(_png()).decode("ascii") not in inputs
    assert "ephemeral" not in options
    caption_mock.assert_awaited_once()

    record = response.metadata["auto_memory_images"]["images"][0]
    assert record["message_id"] == "m1"
    assert record["block_index"] == 1
    source = tmp_path / record["source_path"]
    assert source.read_bytes() == _png()
    assert source.parent == tmp_path / "session" / "images"
    assert source.stem == hashlib.sha256(_png()).hexdigest()
    note_path = record["note_path"]
    assert note_path in response.metadata["image_note_paths"]
    assert f"[[{note_path}]]" in inputs
    note = frontmatter.load(tmp_path / note_path)
    assert note["kind"] == "session_image"
    assert note["source_resource"] == f"[[{record['source_path']}]]"
    assert _CAPTION in note.content
    assert "session_id" not in note.metadata
    assert "source_conversation" not in note.metadata
    assert harness.step._find_session_note([dict(note.metadata, path=note_path)], "s1") is None

    saved = harness.saved()
    assert [block.type for block in saved[0].content] == ["text", "data", "text"]
    saved_image = saved[0].content[1]
    assert saved_image.source.type == "url"
    assert Path(unquote(urlparse(str(saved_image.source.url)).path)) == source
    assert saved[0].metadata["external_id"] == "original"
    assert saved[0].created_at == messages[0].created_at
    assert _CAPTION not in saved[0].model_dump_json()
    assert not (tmp_path / "resource").exists()


@pytest.mark.asyncio
async def test_image_only_turn_survives_text_extraction(tmp_path, caption_mock):
    """A turn without text still contributes its image evidence."""
    harness = _Harness(tmp_path)

    response = await harness.run([_message(_image())], include_images=True)

    assert response.success
    assert _CAPTION in harness.agent.calls[0][0]
    assert "[Sam @" in harness.agent.calls[0][0]
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_images_and_restarted_source_replay_reuse_caption(
    tmp_path,
    caption_mock,
):
    """Content identity survives duplicate occurrences, new Step instances, and caller restart."""
    first = _Harness(tmp_path)
    response = await first.run(
        [_message(_image(), _text("Same board again."), _image())],
        include_images=True,
    )
    assert response.success
    caption_mock.assert_awaited_once()
    records = response.metadata["auto_memory_images"]["images"]
    assert len(records) == 2
    assert records[0]["source_path"] == records[1]["source_path"]
    assert records[0]["note_path"] == records[1]["note_path"]
    assert len(response.metadata["image_note_paths"]) == 1
    source_messages = first.saved()

    restarted = _Harness(tmp_path)
    replay = await restarted.run(
        source_messages,
        include_images=True,
        date="2026-01-03",
    )

    assert replay.success
    caption_mock.assert_awaited_once()
    assert replay.metadata["image_note_paths"] == response.metadata["image_note_paths"]
    assert all(record["cache_hit"] for record in replay.metadata["auto_memory_images"]["images"])
    assert len(list((tmp_path / "session" / "images").iterdir())) == 1
    assert len(list((tmp_path / "daily").rglob("session-image-*.md"))) == 1


@pytest.mark.asyncio
async def test_moved_workspace_replays_saved_relative_image_provenance(
    tmp_path,
    caption_mock,
):
    """Moving user-owned files does not make archived absolute image URLs unusable."""
    original = tmp_path / "original"
    harness = _Harness(original)
    first = await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    moved = tmp_path / "moved"
    original.rename(moved)

    restarted = _Harness(moved)
    response = await restarted.run(saved, include_images=True)

    assert response.success
    assert response.metadata["image_note_paths"] == first.metadata["image_note_paths"]
    assert str(restarted.saved()[0].content[0].source.url).startswith(moved.as_uri())
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_modified_saved_source_fails_instead_of_changing_image_identity(
    tmp_path,
    caption_mock,
):
    """A content-addressed attachment cannot silently become a different source on replay."""
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    source_path = first.metadata["auto_memory_images"]["images"][0]["source_path"]
    (tmp_path / source_path).write_bytes(_png(255))
    harness.agent.calls.clear()

    response = await harness.run(saved, include_images=True)

    assert not response.success
    assert not harness.agent.calls
    caption_mock.assert_awaited_once()
    assert (tmp_path / source_path).read_bytes() == _png(255)


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_source", ["saved-source", "original-input"])
async def test_oversized_stored_asset_is_refused_without_reading_or_overwriting_it(
    tmp_path,
    caption_mock,
    retry_source,
):
    """Every reuse path enforces the byte ceiling on existing user-owned attachments."""
    harness = _Harness(tmp_path)
    original = [_message(_image())]
    first = await harness.run(original, include_images=True)
    saved = harness.saved()
    record = first.metadata["auto_memory_images"]["images"][0]
    asset = tmp_path / record["source_path"]
    note_path = tmp_path / record["note_path"]
    note_before = note_path.read_bytes()
    oversized = _session_images.MAX_IMAGE_INPUT_BYTES + 1
    # Extend this temporary file sparsely instead of allocating a 50 MiB buffer.
    with asset.open("r+b") as image_file:
        image_file.truncate(oversized)
    modified_at = asset.stat().st_mtime_ns
    harness.agent.calls.clear()

    response = await harness.run(
        saved if retry_source == "saved-source" else original,
        include_images=True,
    )

    assert not response.success
    assert response.metadata["auto_memory_images"]["error_stage"] == "source"
    assert not harness.agent.calls
    caption_mock.assert_awaited_once()
    assert asset.stat().st_size == oversized
    assert asset.stat().st_mtime_ns == modified_at
    with asset.open("rb") as image_file:
        assert image_file.read(len(_png())) == _png()
    assert note_path.read_bytes() == note_before


@pytest.mark.asyncio
async def test_saved_provenance_cannot_redirect_to_outside_workspace(
    tmp_path,
    caption_mock,
):
    """Caller-supplied provenance must not bypass workspace containment."""
    harness = _Harness(tmp_path / "workspace")
    first = await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    source = first.metadata["auto_memory_images"]["images"][0]["source_path"]
    outside = tmp_path / Path(source).name
    outside.write_bytes(_png())
    saved[0].metadata["reme_image_sources"][0]["source_path"] = f"../{outside.name}"
    harness.agent.calls.clear()

    response = await harness.run(saved, include_images=True)

    assert not response.success
    assert not harness.agent.calls
    caption_mock.assert_awaited_once()
    assert outside.read_bytes() == _png()


@pytest.mark.asyncio
async def test_caption_prompt_change_creates_new_note_without_duplicating_source(
    tmp_path,
    caption_mock,
):
    """Caption configuration affects reuse while original bytes stay deduplicated."""
    harness = _Harness(tmp_path)
    messages = [_message(_image())]
    first = await harness.run(messages, include_images=True)
    prompt = harness.step.get_prompt("image_caption_prompt")
    harness.step.prompt.load_prompt_dict(
        {"image_caption_prompt": prompt + "\nInclude readable serial numbers."},
    )

    second = await harness.run(messages, include_images=True)

    assert second.success
    assert caption_mock.await_count == 2
    assert second.metadata["image_note_paths"] != first.metadata["image_note_paths"]
    assert len(list((tmp_path / "session" / "images").iterdir())) == 1


@pytest.mark.asyncio
async def test_user_edited_image_note_remains_caption_source_of_truth(
    tmp_path,
    caption_mock,
):
    """Reusing image memory respects user corrections in its durable note."""
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image())], include_images=True)
    note_path = tmp_path / first.metadata["image_note_paths"][0]
    note = frontmatter.load(note_path)
    note.content = "User-corrected caption: the board reads ORBIT-43."
    note_path.write_text(frontmatter.dumps(note), encoding="utf-8")
    modified = note_path.read_bytes()

    response = await harness.run(harness.saved(), include_images=True)

    assert response.success
    assert "User-corrected caption: the board reads ORBIT-43." in harness.agent.calls[-1][0]
    assert note_path.read_bytes() == modified
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_id_retry_upgrades_previously_text_only_saved_source(
    tmp_path,
    caption_mock,
):
    """The JSONL append optimization cannot discard an image reference added on retry."""
    harness = _Harness(tmp_path)
    messages = [_message(_text("Remember this board."), _image())]
    await harness.run(messages, include_images=False)
    assert [block.type for block in harness.saved()[0].content] == ["text"]

    response = await harness.run(messages, include_images=True)

    assert response.success
    saved = harness.saved()
    assert len(saved) == 1
    assert [block.type for block in saved[0].content] == ["text", "data"]
    assert saved[0].content[1].source.type == "url"
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_card_links_survive_full_agent_rewrite_and_increment(
    tmp_path,
    caption_mock,
):
    """Distinct image-card links are unioned even when the agent replaces frontmatter."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    first = await harness.run(
        [_message(_text("First board."), _image())],
        include_images=True,
    )
    first_links = {f"[[{path}]]" for path in first.metadata["image_note_paths"]}
    session_path = tmp_path / first.metadata["path"]
    assert set(frontmatter.load(session_path)["image_notes"]) == first_links

    second = await harness.run(
        [_message(_image(_png(255)), msg_id="m2")],
        include_images=True,
    )

    assert second.success
    assert second.metadata["path"] == first.metadata["path"]
    expected = first_links | {f"[[{path}]]" for path in second.metadata["image_note_paths"]}
    assert set(frontmatter.load(session_path)["image_notes"]) == expected
    assert len(expected) == 2
    assert caption_mock.await_count == 2


@pytest.mark.asyncio
async def test_text_only_increment_keeps_existing_image_links_when_images_enabled(
    tmp_path,
    caption_mock,
):
    """An enabled session retains source links even when the new turn has no image."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    first = await harness.run([_message(_image())], include_images=True)
    note_path = tmp_path / first.metadata["path"]
    original_links = frontmatter.load(note_path)["image_notes"]

    response = await harness.run(
        [_message(_text("The board is now approved."), msg_id="m2")],
        include_images=True,
    )

    assert response.success
    assert frontmatter.load(note_path)["image_notes"] == original_links
    assert response.metadata["auto_memory_images"]["image_count"] == 0
    assert isinstance(harness.agent.calls[-1][0], str)
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_results_and_nonimage_data_never_become_image_memory(
    tmp_path,
    caption_mock,
):
    """Only image blocks directly in conversation content are extracted."""
    harness = _Harness(tmp_path)
    message = _message(
        _text("Plain evidence."),
        _url("https://example.com/audio.mp3", "audio/mpeg"),
        {
            "type": "tool_result",
            "id": "tool-call-1",
            "name": "read_image",
            "output": [_image()],
        },
        role="assistant",
    )

    response = await harness.run([message], include_images=True)

    assert response.success
    caption_mock.assert_not_awaited()
    assert "Plain evidence." in harness.agent.calls[0][0]
    assert _CAPTION not in harness.agent.calls[0][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("default,override", [(True, False), (False, True)])
async def test_call_switch_overrides_configured_default(
    tmp_path,
    caption_mock,
    default,
    override,
):
    """A caller can enable or disable images independently of the job default."""
    harness = _Harness(tmp_path, include_images=default)

    response = await harness.run([_message(_image())], include_images=override)

    assert response.success
    assert caption_mock.await_count == int(override)
    assert isinstance(harness.agent.calls[0][0], str)


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["missing-dialog-scope", "dialog-symlink"])
async def test_transcript_access_is_checked_before_any_image_side_effect(
    tmp_path,
    caption_mock,
    monkeypatch,
    denial,
):
    """Rejected transcript destinations cannot trigger a download or materialize sources."""
    harness = _Harness(tmp_path / "workspace")
    client = MagicMock(side_effect=AssertionError("HTTP client must not be created"))
    monkeypatch.setattr(_session_images.httpx, "AsyncClient", client)
    call_kwargs = {}
    outside = tmp_path / "outside-dialog"
    outside.mkdir()
    if denial == "missing-dialog-scope":
        call_kwargs["_allowed_paths"] = ["session/images", "daily"]
    else:
        (harness.path / "session").mkdir()
        (harness.path / "session" / "dialog").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="permission|workspace"):
        await harness.run(
            [_message(_url("https://example.com/board.png"))],
            include_images=True,
            **call_kwargs,
        )

    client.assert_not_called()
    caption_mock.assert_not_awaited()
    assert not harness.agent.calls
    assert not (harness.path / "session" / "images").exists()
    assert not (harness.path / "session" / "dialog" / "s1.jsonl").exists()
    assert not (harness.path / "daily").exists()
    assert not list(outside.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("escape", ["direct", "symlink", "remote-file-host"])
async def test_local_image_cannot_read_outside_workspace(
    tmp_path,
    caption_mock,
    escape,
):
    """Direct paths, escaping symlinks, and nonlocal file hosts are refused."""
    outside = tmp_path / "private.png"
    outside.write_bytes(_png())
    harness = _Harness(tmp_path / "workspace")
    if escape == "direct":
        source_url = outside.as_uri()
    elif escape == "symlink":
        link = harness.path / "external.png"
        link.symlink_to(outside)
        source_url = link.as_uri()
    else:
        source_url = "file://other-host/private.png"

    response = await harness.run([_message(_url(source_url))], include_images=True)

    assert not response.success
    caption_mock.assert_not_awaited()
    assert not harness.agent.calls
    assert outside.read_bytes() == _png()
    assert not (harness.path / "daily").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["ftp://example.com/board.png", "https://user:password@example.com/board.png"],
)
async def test_unsupported_or_credentialed_url_never_opens_http_client(
    tmp_path,
    caption_mock,
    monkeypatch,
    url,
):
    """Reject invalid sources before any network resource is created."""
    client = MagicMock(side_effect=AssertionError("HTTP client must not be created"))
    monkeypatch.setattr(_session_images.httpx, "AsyncClient", client)
    harness = _Harness(tmp_path)

    response = await harness.run([_message(_url(url))], include_images=True)

    assert not response.success
    client.assert_not_called()
    caption_mock.assert_not_awaited()
    assert not harness.agent.calls


@pytest.mark.asyncio
async def test_remote_image_is_downloaded_once_and_replayed_locally(
    tmp_path,
    caption_mock,
    monkeypatch,
):
    """Saved image messages no longer depend on the availability of their URL."""
    requested = []

    def handle(request):
        requested.append(str(request.url))
        return httpx.Response(
            200,
            content=_png(),
            headers={"content-type": "image/png"},
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        _session_images.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs),
    )
    harness = _Harness(tmp_path)
    first = await harness.run(
        [_message(_url("https://example.com/board.png"))],
        include_images=True,
    )
    second = await harness.run(harness.saved(), include_images=True)

    assert first.success and second.success
    assert requested == ["https://example.com/board.png"]
    assert first.metadata["image_note_paths"] == second.metadata["image_note_paths"]
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_remote_failure_does_not_expose_signed_url_in_response(
    tmp_path,
    caption_mock,
    monkeypatch,
):
    """Transport failures must not publish credentials carried in a signed URL."""
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        _session_images.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(
            transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
            **kwargs,
        ),
    )
    harness = _Harness(tmp_path)

    response = await harness.run(
        [_message(_url("https://example.com/board.png?signature=do-not-publish-this"))],
        include_images=True,
    )

    assert not response.success
    assert "do-not-publish-this" not in str(response)
    caption_mock.assert_not_awaited()
    assert not harness.agent.calls


@pytest.mark.asyncio
async def test_concurrent_sessions_share_one_caption_for_identical_image(
    tmp_path,
    caption_mock,
):
    """Simultaneous occurrences share a single caption computation."""

    async def caption(*_args):
        await asyncio.sleep(0)
        return caption_mock.return_value

    caption_mock.side_effect = caption
    first = _Harness(tmp_path)
    second = _Harness(tmp_path)

    results = await asyncio.wait_for(
        asyncio.gather(
            first.run([_message(_image())], session_id="first", include_images=True),
            second.run([_message(_image())], session_id="second", include_images=True),
        ),
        timeout=5,
    )

    assert all(result.success for result in results)
    caption_mock.assert_awaited_once()
    assert results[0].metadata["image_note_paths"] == results[1].metadata["image_note_paths"]
    assert first.saved("first")
    assert second.saved("second")


@pytest.mark.asyncio
async def test_concurrent_same_session_keeps_both_messages_and_image_links(
    tmp_path,
    caption_mock,
):
    """Concurrent session updates cannot lose messages or previous image provenance."""
    first = _Harness(tmp_path)
    second = _Harness(tmp_path)
    first.write_session_card_on_reply()
    second.write_session_card_on_reply()

    results = await asyncio.wait_for(
        asyncio.gather(
            first.run([_message(_image(), msg_id="first")], include_images=True),
            second.run(
                [_message(_image(_png(255)), msg_id="second")],
                include_images=True,
            ),
        ),
        timeout=5,
    )

    assert all(result.success for result in results)
    assert {message.id for message in first.saved()} == {"first", "second"}
    links = {f"[[{path}]]" for result in results for path in result.metadata["image_note_paths"]}
    assert set(frontmatter.load(tmp_path / "daily" / _DAY / "memory.md")["image_notes"]) == links
    assert len(links) == 2
    assert caption_mock.await_count == 2


@pytest.mark.asyncio
async def test_enabled_text_delta_waits_for_concurrent_image_memory(
    tmp_path,
    caption_mock,
):
    """A text-only delta cannot read stale session state while an image run is writing it."""
    image_run = _Harness(tmp_path)
    text_run = _Harness(tmp_path)
    image_run.write_session_card_on_reply()
    text_run.write_session_card_on_reply()
    image_writer = image_run.agent.on_reply
    text_writer = text_run.agent.on_reply
    image_agent_started = asyncio.Event()
    text_agent_started = asyncio.Event()
    release_image_agent = asyncio.Event()

    async def write_image_memory():
        image_agent_started.set()
        await release_image_agent.wait()
        await image_writer()

    async def write_text_memory():
        text_agent_started.set()
        await text_writer()

    image_run.agent.on_reply = write_image_memory
    text_run.agent.on_reply = write_text_memory
    image_task = asyncio.create_task(
        image_run.run([_message(_image(), msg_id="image-turn")], include_images=True),
    )
    await asyncio.wait_for(image_agent_started.wait(), timeout=5)
    text_task = asyncio.create_task(
        text_run.run(
            [_message(_text("The board is approved."), msg_id="text-turn")],
            include_images=True,
        ),
    )
    text_was_blocked = False
    try:
        # The image agent remains paused, so entering the text agent during
        # this interval would necessarily mean concurrent session mutation.
        await asyncio.wait_for(text_agent_started.wait(), timeout=0.1)
    except TimeoutError:
        text_was_blocked = True
    finally:
        release_image_agent.set()
    results = await asyncio.wait_for(asyncio.gather(image_task, text_task), timeout=5)

    assert text_was_blocked
    assert all(result.success for result in results)
    assert {message.id for message in image_run.saved()} == {"image-turn", "text-turn"}
    image_links = [f"[[{path}]]" for path in results[0].metadata["image_note_paths"]]
    assert frontmatter.load(tmp_path / "daily" / _DAY / "memory.md")["image_notes"] == image_links
    assert "Target path:" in text_run.agent.calls[0][0]
    caption_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_image_processing_failure_preserves_source_for_retry_and_skips_agent(
    tmp_path,
    caption_mock,
):
    """Caption failures leave original evidence available for a later retry."""
    harness = _Harness(tmp_path)
    caption_mock.side_effect = RuntimeError("temporary vision failure")

    failed = await harness.run(
        [_message(_text("Board to remember."), _image())],
        include_images=True,
    )

    assert not failed.success
    assert not harness.agent.calls
    saved = harness.saved()
    assert saved[0].content[1].source.type == "url"
    assert not list((tmp_path / "daily").rglob("session-image-*.md"))

    caption_mock.side_effect = None
    retried = await harness.run(saved, include_images=True)

    assert retried.success
    assert len(retried.metadata["image_note_paths"]) == 1
    assert len(harness.agent.calls) == 1


@pytest.mark.asyncio
async def test_partial_caption_failure_is_reported_and_successful_card_is_reused(
    tmp_path,
    caption_mock,
):
    """Retry completes missing captions without repeating successful work."""
    harness = _Harness(tmp_path)
    caption_mock.side_effect = [
        caption_mock.return_value,
        RuntimeError("second image failed"),
    ]
    failed = await harness.run(
        [_message(_image(), _image(_png(255)))],
        include_images=True,
    )

    assert not failed.success
    assert not harness.agent.calls
    assert failed.metadata["auto_memory_images"]["image_count"] == 2
    assert failed.metadata["auto_memory_images"]["ready_count"] == 1
    assert [item["status"] for item in failed.metadata["auto_memory_images"]["images"]] == ["ready", "failed"]
    assert len(failed.metadata["image_note_paths"]) == 1
    caption_mock.side_effect = None

    retried = await harness.run(harness.saved(), include_images=True)

    assert retried.success
    assert caption_mock.await_count == 3
    assert retried.metadata["auto_memory_images"]["cache_hits"] == 1
    assert len(retried.metadata["image_note_paths"]) == 2


@pytest.mark.asyncio
async def test_custom_session_directory_contains_images_and_transcript(
    tmp_path,
    caption_mock,
):
    """Custom session locations apply equally to transcripts and image sources."""
    harness = _Harness(tmp_path, session_dir="conversations")

    response = await harness.run([_message(_image())], include_images=True)

    assert response.success
    record = response.metadata["auto_memory_images"]["images"][0]
    assert record["source_path"].startswith("conversations/images/")
    assert harness.saved()[0].content[0].source.type == "url"
    assert not (tmp_path / "session").exists()
    caption_mock.assert_awaited_once()


def test_default_config_keeps_auto_memory_images_opt_in():
    """The job default and its public schema agree on backward compatibility."""
    job = _load_config("default.yaml")["jobs"]["auto_memory"]
    parameter = job["parameters"]["properties"]["include_images"]

    assert job["include_images"] is False
    assert parameter["type"] == "boolean"
    assert parameter["default"] is False
    assert "include_images" not in job["parameters"].get("required", [])
