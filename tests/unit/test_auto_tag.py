"""Focused tests for the standalone automatic tagging Step."""

# pylint: disable=missing-function-docstring

from pathlib import Path

import frontmatter
import pytest

from reme.components.agent_wrapper import BaseAgentWrapper
from reme.components.file_store import LocalFileStore
from reme.components.runtime_context import RuntimeContext
from reme.components.tag_index import LocalTagIndex
from reme.schema import Response
from reme.steps.evolve.auto_tag import AutoTagStep, normalize_memory_tags


class _TaggingWrapper(BaseAgentWrapper):
    def __init__(
        self,
        workspace: Path,
        *,
        fail_name: str = "",
        tag_key: str = "memory_tags",
        tags: list[object] | None = None,
    ) -> None:
        super().__init__(name="tagger")
        self.workspace = workspace
        self.fail_name = fail_name
        self.tag_key = tag_key
        self.tags = ["宁德时代", "黄金"] if tags is None else tags
        self.calls: list[tuple[str, dict]] = []

    async def reply(self, inputs, **kwargs) -> dict:
        text = str(inputs)
        self.calls.append((text, kwargs))
        path = kwargs["injected_job_kwargs"]["_allowed_paths"][0]
        if Path(path).name == self.fail_name:
            raise RuntimeError("tagging failed")
        target = self.workspace / path
        post = frontmatter.loads(target.read_text(encoding="utf-8"))
        post.metadata[self.tag_key] = self.tags
        target.write_text(frontmatter.dumps(post), encoding="utf-8")
        return {"result": f"tagged {path}", "last_message": {}}


def _write_note(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nname: note\ndescription: useful note\n---\nbody\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_auto_tag_handles_noop_and_rejects_invalid_preconditions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wrapper = _TaggingWrapper(tmp_path)
    unindexed_store = LocalFileStore(name="store", embedding_store="", tag_index="")

    context = RuntimeContext(changes=[])
    context.response.answer = "Skipped: no messages"
    response = await AutoTagStep(file_store=unindexed_store, agent_wrapper=wrapper)(context)
    assert response.success is True
    assert response.answer == "Skipped: no messages"
    assert response.metadata["auto_tag"]["processed"] == 0

    response = await AutoTagStep(file_store=unindexed_store, agent_wrapper=wrapper)(
        RuntimeContext(changes="daily/note.md"),
    )
    assert response.success is False
    assert response.answer == "AutoTagStep requires changes: list[dict]"

    note = tmp_path / "daily/2026-09-09/note.md"
    _write_note(note)
    before = note.read_bytes()
    change = RuntimeContext(changes=[{"change": "added", "path": "daily/2026-09-09/note.md"}])
    response = await AutoTagStep(file_store=unindexed_store, agent_wrapper=wrapper)(change)

    assert response.success is False
    assert response.answer == "Error: tag index is not configured"
    assert not wrapper.calls
    assert note.read_bytes() == before

    indexed_store = LocalFileStore(name="store", embedding_store="", tag_index="")
    indexed_store.tag_index = LocalTagIndex(max_tags_per_file=2)
    response = await AutoTagStep(
        file_store=indexed_store,
        agent_wrapper=wrapper,
        max_tags_per_file=3,
    )(RuntimeContext(changes=[{"change": "added", "path": "daily/2026-09-09/note.md"}]))
    assert response.success is False
    assert response.answer == "Error: auto_tag max_tags_per_file (3) exceeds tag index limit (2)"
    assert not wrapper.calls
    assert note.read_bytes() == before


@pytest.mark.asyncio
async def test_auto_tag_filters_paths_and_continues_after_one_file_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "daily/2026-09-09/first.md"
    failed = tmp_path / "daily/2026-09-09/failed.md"
    _write_note(first)
    _write_note(failed)
    (tmp_path / "daily/2026-09-09/notes").mkdir()
    (tmp_path / "daily/2026-09-09/plain.txt").write_text("text", encoding="utf-8")

    store = LocalFileStore(name="store", embedding_store="", tag_index="")
    store.tag_index = LocalTagIndex()
    wrapper = _TaggingWrapper(tmp_path, fail_name="failed.md")
    step = AutoTagStep(file_store=store, agent_wrapper=wrapper)
    context = RuntimeContext(
        changes=[
            {"change": "modified", "path": "daily/2026-09-09/failed.md"},
            {"change": "added", "path": "daily/2026-09-09/notes"},
            {"change": "added", "path": "daily/2026-09-09/plain.txt"},
            {"change": "modified", "path": "daily/2026-09-09/first.md"},
            {"change": "added", "path": "daily/2026-09-09/first.md"},
            {"change": "deleted", "path": "daily/2026-09-09/deleted.md"},
        ],
    )

    response = await step(context)

    assert response.success is False
    assert [call[1]["injected_job_kwargs"] for call in wrapper.calls] == [
        {
            "_allowed_paths": ["daily/2026-09-09/failed.md"],
            "_allowed_frontmatter_keys": ["memory_tags"],
        },
        {
            "_allowed_paths": ["daily/2026-09-09/first.md"],
            "_allowed_frontmatter_keys": ["memory_tags"],
        },
    ]
    assert all(
        call[1]["job_tools"] == ["read", "list_tags", "frontmatter_read", "frontmatter_update"]
        for call in wrapper.calls
    )
    assert frontmatter.loads(first.read_text(encoding="utf-8")).metadata["memory_tags"] == ["宁德时代", "黄金"]
    assert "memory_tags" not in frontmatter.loads(failed.read_text(encoding="utf-8")).metadata
    assert response.metadata["auto_tag"]["processed"] == 2
    assert response.metadata["auto_tag"]["succeeded"] == 1
    assert response.metadata["auto_tag"]["failed"] == 1
    assert response.metadata["auto_tag"]["ignored"] == [
        {"path": "daily/2026-09-09/notes", "reason": "not a file"},
        {"path": "daily/2026-09-09/plain.txt", "reason": "not a Markdown file"},
        {"path": "daily/2026-09-09/deleted.md", "reason": "unsupported change: deleted"},
    ]
    assert response.metadata["auto_tag"]["results"] == [
        {
            "change": "modified",
            "path": "daily/2026-09-09/failed.md",
            "success": False,
            "error": "tagging failed",
        },
        {
            "change": "added",
            "path": "daily/2026-09-09/first.md",
            "success": True,
            "summary": "tagged daily/2026-09-09/first.md",
        },
    ]
    assert "memory_tags: ['宁德时代', '黄金']" in (tmp_path / "daily/2026-09-09.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_auto_tag_uses_configured_key_and_normalizes_agent_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "memory/note.md"
    _write_note(note)
    store = LocalFileStore(name="store", embedding_store="", tag_index="")
    store.tag_index = LocalTagIndex(tag_key="keywords", max_tag_length=8)
    wrapper = _TaggingWrapper(
        tmp_path,
        tag_key="keywords",
        tags=["OpenAI", "openai", "Sam   Altman", "++", 100, "宁德时代", "黄金"],
    )
    step = AutoTagStep(file_store=store, agent_wrapper=wrapper, max_tags_per_file=2)

    async def update_frontmatter(name, /, **kwargs):
        assert name == "frontmatter_update"
        assert kwargs["_allowed_frontmatter_keys"] == ["keywords"]
        post = frontmatter.loads(note.read_text(encoding="utf-8"))
        post.metadata.update(kwargs["metadata"])
        note.write_text(frontmatter.dumps(post), encoding="utf-8")
        return Response(answer="updated")

    monkeypatch.setattr(step, "run_job", update_frontmatter)

    context = RuntimeContext(changes=[{"change": "modified", "path": "memory/note.md"}])
    context.response.answer = "Created memory/note.md"
    response = await step(context)

    assert response.success is True
    assert response.answer == "Created memory/note.md"
    assert frontmatter.loads(note.read_text(encoding="utf-8")).metadata["keywords"] == [
        "OpenAI",
        "宁德时代",
    ]
    assert normalize_memory_tags(
        ["one", "two", "three"],
        max_tags_per_file=2,
        max_tag_length=3,
    ) == ["one", "two"]
