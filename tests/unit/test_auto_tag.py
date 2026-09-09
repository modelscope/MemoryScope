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
from reme.steps.evolve.auto_tag import AutoTagStep, normalize_tags


class _TaggingWrapper(BaseAgentWrapper):
    def __init__(
        self,
        workspace: Path,
        *,
        fail_name: str = "",
        tag_key: str = "tags",
        tags: list[object] | None = None,
    ) -> None:
        super().__init__(name="tagger")
        self.workspace = workspace
        self.fail_name = fail_name
        self.tag_key = tag_key
        self.tags = ["ReMe", "Python"] if tags is None else tags
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
async def test_auto_tag_requires_tag_index_before_modifying_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "daily/2026-09-09/note.md"
    _write_note(note)
    before = note.read_bytes()
    store = LocalFileStore(name="store", embedding_store="", tag_index="")
    wrapper = _TaggingWrapper(tmp_path)
    step = AutoTagStep(file_store=store, agent_wrapper=wrapper)

    response = await step(RuntimeContext(modified_paths=["daily/2026-09-09/note.md"]))

    assert response.success is False
    assert response.answer == "Error: tag index is not configured"
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
        modified_paths=[
            "daily/2026-09-09/failed.md",
            "daily/2026-09-09/notes",
            "daily/2026-09-09/plain.txt",
            "daily/2026-09-09/first.md",
            "daily/2026-09-09/first.md",
        ],
    )

    response = await step(context)

    assert response.success is False
    assert [call[1]["injected_job_kwargs"] for call in wrapper.calls] == [
        {
            "_allowed_paths": ["daily/2026-09-09/failed.md"],
            "_allowed_frontmatter_keys": ["tags"],
        },
        {
            "_allowed_paths": ["daily/2026-09-09/first.md"],
            "_allowed_frontmatter_keys": ["tags"],
        },
    ]
    assert all(
        call[1]["job_tools"] == ["read", "list_tags", "frontmatter_read", "frontmatter_update"]
        for call in wrapper.calls
    )
    assert frontmatter.loads(first.read_text(encoding="utf-8")).metadata["tags"] == ["ReMe", "Python"]
    assert "tags" not in frontmatter.loads(failed.read_text(encoding="utf-8")).metadata
    assert response.metadata["auto_tag"]["tagged_paths"] == ["daily/2026-09-09/first.md"]
    assert response.metadata["auto_tag"]["ignored_paths"] == [
        "daily/2026-09-09/notes",
        "daily/2026-09-09/plain.txt",
    ]
    assert response.metadata["auto_tag"]["failed_paths"] == [
        {"path": "daily/2026-09-09/failed.md", "error": "tagging failed"},
    ]
    assert "tags: ['ReMe', 'Python']" in (tmp_path / "daily/2026-09-09.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_auto_tag_uses_configured_key_and_normalizes_agent_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "memory/note.md"
    _write_note(note)
    store = LocalFileStore(name="store", embedding_store="", tag_index="")
    store.tag_index = LocalTagIndex(tag_key="keywords")
    wrapper = _TaggingWrapper(
        tmp_path,
        tag_key="keywords",
        tags=["ReMe", "reme", "memory system", "++", 100],
    )
    step = AutoTagStep(file_store=store, agent_wrapper=wrapper)

    async def update_frontmatter(name, /, **kwargs):
        assert name == "frontmatter_update"
        assert kwargs["_allowed_frontmatter_keys"] == ["keywords"]
        post = frontmatter.loads(note.read_text(encoding="utf-8"))
        post.metadata.update(kwargs["metadata"])
        note.write_text(frontmatter.dumps(post), encoding="utf-8")
        return Response(answer="updated")

    monkeypatch.setattr(step, "run_job", update_frontmatter)

    response = await step(RuntimeContext(modified_paths=["memory/note.md"]))

    assert response.success is True
    assert frontmatter.loads(note.read_text(encoding="utf-8")).metadata["keywords"] == ["ReMe", "100"]
    assert "Tag field: keywords" in wrapper.calls[0][0]
    assert "`keywords`" in wrapper.calls[0][1]["system_prompt"]


def test_normalize_tags_enforces_storage_contract():
    assert normalize_tags(
        [
            "GPT-5",
            "C++",
            "C#",
            ".NET",
            100,
            "memory system",
            "++",
            "ReMe",
            "reme",
            "tag7",
            "tag8",
            "tag9",
        ],
    ) == ["GPT-5", "C++", "C#", ".NET", "100", "ReMe", "tag7", "tag8"]
