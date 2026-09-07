"""Regression tests for canonical memory subjects and shared recall."""

# pylint: disable=protected-access

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import frontmatter

from reme.components.file_chunker import MarkdownFileChunker
from reme.components.agent_wrapper import BaseAgentWrapper
from reme.components.file_store import BaseFileStore, LocalFileStore
from reme.components.application_context import ApplicationContext
from reme.components.runtime_context import RuntimeContext
from reme.enumeration import LinkScopeEnum
from reme.schema import FileChunk, FileLink, FileNode, normalized_subject
from reme.steps.evolve.auto_memory import AutoMemoryStep
from reme.steps.evolve.dream.extract import DreamExtractStep
from reme.steps.evolve.dream.integrate import DreamIntegrateStep
from reme.steps.index.search import SearchStep


def test_subject_alias_is_deterministic_and_canonical_wins():
    assert normalized_subject({"target": "legacy-person"}) == "legacy-person"
    assert normalized_subject({"subject": "new-person", "target": "legacy-person"}) == "new-person"
    assert normalized_subject({"subject": "  ", "target": "legacy-person"}) == "legacy-person"


def test_markdown_chunks_normalize_legacy_subject_and_shared_marker(tmp_path):
    path = tmp_path / "daily" / "2026-09-01" / "memory.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nname: memory\ntarget: project-alpha\nshared: false\n---\n# body\n",
        encoding="utf-8",
    )
    chunker = MarkdownFileChunker(
        max_ast_sections=0,
        include_frontmatter_in_metadata=True,
        include_frontmatter_keys_in_metadata=["subject", "shared", "kind"],
    )
    _, chunks = asyncio.run(chunker.chunk(path))
    assert chunks[0].metadata == {"subject": "project-alpha"}

    path.write_text("---\nname: memory\nshared: true\n---\n# body\n", encoding="utf-8")
    _, chunks = asyncio.run(chunker.chunk(path))
    assert chunks[0].metadata == {"shared": True}


def test_local_store_subject_filter_is_subject_or_explicit_shared():
    personal = FileChunk(id="personal", path="daily/personal.md", text="x", metadata={"subject": "alpha"})
    shared = FileChunk(id="shared", path="digest/shared.md", text="x", metadata={"shared": True})
    unscoped = FileChunk(id="unscoped", path="daily/unscoped.md", text="x", metadata={})
    search_filter = {"metadata_any": [{"subject": "alpha"}, {"shared": True}]}

    assert LocalFileStore._matches_search_filter(personal, search_filter)
    assert LocalFileStore._matches_search_filter(shared, search_filter)
    assert not LocalFileStore._matches_search_filter(unscoped, search_filter)


class _SearchStore(BaseFileStore):
    """Small search store that records the public filter passed by SearchStep."""

    def __init__(self, chunks):
        super().__init__(name="subject-search")
        self.chunks = chunks
        self.filters = []

    async def upsert(self, files: list[tuple[FileNode, list[FileChunk]]]) -> None:
        del files

    async def delete(self, path: str | list[str]) -> None:
        del path

    async def clear(self) -> None:
        return None

    async def get_nodes(self, paths: list[str] | None = None) -> list[FileNode]:
        del paths
        return []

    async def get_outlinks(self, path: str, scope: LinkScopeEnum = LinkScopeEnum.REAL) -> list[FileLink]:
        del path, scope
        return []

    async def get_inlinks(self, path: str, scope: LinkScopeEnum = LinkScopeEnum.REAL) -> list[FileLink]:
        del path, scope
        return []

    async def vector_search(self, query: str, limit: int, search_filter: dict) -> list[FileChunk]:
        del query
        self.filters.append(search_filter)
        return self.chunks[:limit]

    async def keyword_search(self, query: str, limit: int, search_filter: dict) -> list[FileChunk]:
        del query
        self.filters.append(search_filter)
        return self.chunks[:limit]


def test_search_step_exposes_subject_or_shared_policy():
    store = _SearchStore([FileChunk(id="c", path="daily/a.md", text="memory", scores={"score": 1.0})])

    async def run():
        step = SearchStep(file_store=store, expand_links=False, vector_weight=0.0)
        response = await step(RuntimeContext(query="memory", subject="alpha", limit=5))
        assert response.metadata["subject_scope"]["policy"] == "subject match OR explicit shared:true"

    asyncio.run(run())
    assert store.filters == [{"metadata_any": [{"subject": "alpha"}, {"shared": True}]}]


def test_auto_memory_rejects_existing_subject_conflict(tmp_path):
    note_path = tmp_path / "daily" / "2026-09-01" / "memory.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text("---\nsession_id: s1\nsubject: alpha\n---\nold\n", encoding="utf-8")
    store = LocalFileStore(
        name="subject-memory",
        embedding_store="",
        app_context=ApplicationContext(workspace_dir=str(tmp_path)),
    )
    step = AutoMemoryStep(file_store=store)
    reply = AsyncMock()
    step.agent_wrapper = SimpleNamespace(reply=reply)

    async def list_note(_day, _session_id):
        return {"path": "daily/2026-09-01/memory.md", "session_id": "s1"}

    step._list_session_note = list_note
    response = asyncio.run(
        step(
            RuntimeContext(
                messages=[{"name": "user", "role": "user", "content": "new", "created_at": "2026-09-01T10:00:00"}],
                session_id="s1",
                date="2026-09-01",
                subject="beta",
            ),
        ),
    )
    response = response or step.context.response
    assert response.success is False
    assert "subject mismatch" in response.answer
    reply.assert_not_awaited()


def test_auto_memory_frontmatter_repair_preserves_exact_subject(tmp_path):
    note_path = tmp_path / "daily" / "2026-09-01" / "memory.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text("---\nname: memory\n---\nbody\n", encoding="utf-8")
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=tmp_path)
    async def update_frontmatter(*_args, **kwargs):
        post = frontmatter.loads(note_path.read_text(encoding="utf-8"))
        post.metadata.update(kwargs["metadata"])
        note_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return SimpleNamespace(success=True, answer="ok")

    step.run_job = AsyncMock(side_effect=update_frontmatter)

    asyncio.run(step._ensure_memory_frontmatter("daily/2026-09-01/memory.md", "s1", "alpha"))

    metadata = frontmatter.loads(note_path.read_text(encoding="utf-8")).metadata
    assert metadata["subject"] == "alpha"
    assert step.run_job.await_args.kwargs["metadata"]["subject"] == "alpha"


def test_auto_memory_create_repairs_model_note_to_caller_subject(tmp_path):
    note_path = "daily/2026-09-01/memory.md"

    class _CreateWrapper(BaseAgentWrapper):
        async def reply(self, *_args, **_kwargs):
            note_file.parent.mkdir(parents=True, exist_ok=True)
            note_file.write_text("---\nname: memory\n---\nbody\n", encoding="utf-8")
            return {"result": "created"}

    store = LocalFileStore(
        name="subject-create",
        embedding_store="",
        app_context=ApplicationContext(workspace_dir=str(tmp_path)),
    )
    note_file = tmp_path / note_path
    step = AutoMemoryStep(file_store=store, agent_wrapper=_CreateWrapper(name="fake"))

    listed_paths = iter([None, {"path": note_path, "session_id": "s1"}])

    async def list_note(_day, _session_id):
        return next(listed_paths)

    async def update_frontmatter(*_args, **kwargs):
        post = frontmatter.loads(note_file.read_text(encoding="utf-8"))
        post.metadata.update(kwargs["metadata"])
        note_file.write_text(frontmatter.dumps(post), encoding="utf-8")
        return SimpleNamespace(success=True, answer="ok")

    step._list_session_note = list_note
    step.run_job = AsyncMock(side_effect=update_frontmatter)

    with patch("reme.steps.evolve.auto_memory.refresh_day_index", new=AsyncMock(return_value={})):
        response = asyncio.run(
            step(
                RuntimeContext(
                    messages=[
                        {
                            "name": "user",
                            "role": "user",
                            "content": "remember this",
                            "created_at": "2026-09-01T10:00:00",
                        },
                    ],
                    session_id="s1",
                    date="2026-09-01",
                    subject="alpha",
                ),
            ),
        )

    response = response or step.context.response
    assert response.success is True
    assert response.metadata["created"] is True
    assert frontmatter.loads(note_file.read_text(encoding="utf-8")).metadata["subject"] == "alpha"
    assert step.run_job.await_args.kwargs["metadata"]["subject"] == "alpha"


def test_dream_extract_drops_units_that_merge_different_subjects(tmp_path):
    first = tmp_path / "daily" / "2026-09-01" / "a.md"
    second = tmp_path / "daily" / "2026-09-01" / "b.md"
    first.parent.mkdir(parents=True)
    first.write_text("---\nsubject: alpha\n---\na\n", encoding="utf-8")
    second.write_text("---\nsubject: beta\n---\nb\n", encoding="utf-8")
    step = DreamExtractStep()
    step._path_scopes = step._load_path_scopes(tmp_path, ["daily/2026-09-01/a.md", "daily/2026-09-01/b.md"])
    state = SimpleNamespace(changed_paths=list(step._path_scopes), units=[], warnings=[])

    step.clean_output(
        state,
        {
            "units": [
                {
                    "name": "merged",
                    "bucket": "personal",
                    "summary": "merged summary",
                    "paths": list(step._path_scopes),
                },
            ],
        },
    )

    assert state.units == []
    assert "different subjects" in state.warnings[0]


def test_dream_integrate_rejects_incompatible_existing_subject(tmp_path):
    target = tmp_path / "digest" / "personal" / "alpha.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nsubject: beta\n---\nbody\n", encoding="utf-8")
    assert not DreamIntegrateStep._valid_target(
        tmp_path,
        "digest",
        "personal",
        "digest/personal/alpha.md",
        action="REFINE",
        existed_before=True,
        expected_subject="alpha",
    )
