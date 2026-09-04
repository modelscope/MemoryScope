"""Regression tests for the safety findings from the Auto Resource PR review."""

from unittest.mock import patch

import frontmatter
import pytest

from reme.steps.evolve.base_auto_resource import BaseAutoResourceStep

from .auto_resource_test_support import (
    FakeVisionModel,
    StructuredVisionModel,
    caption_json,
    image_bytes,
    write_binary,
    write_note,
)

pytest_plugins = ("unit.auto_resource_test_plugin",)
pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_image_rejects_paths_outside_the_resource_tree(routed, auto_resource_env, tmp_path):
    """Traversal and external paths fail before image reads."""
    env = auto_resource_env
    outside = write_binary(tmp_path / "outside.png", image_bytes())
    nonresource = env.write_binary("private.png", image_bytes())

    model = FakeVisionModel(caption_json("unsafe", "Unsafe", "Must not be read."))
    response = await env.run(
        env.processor(model, routed=routed),
        [
            {"change": "added", "path": "resource/2026-01-01/../../../outside.png"},
            {"change": "added", "path": str(outside)},
            {"change": "added", "path": str(nonresource)},
        ],
    )

    results = response.metadata["results"]
    assert response.success is False
    assert len(results) == 3
    assert all(item["metadata"]["action"] == "failed" for item in results)
    assert all(item["metadata"]["modified"] is False for item in results)
    assert "cannot contain '.' or '..'" in results[0]["metadata"]["error"]
    assert "must stay inside the workspace" in results[1]["metadata"]["error"]
    assert "configured resource directory" in results[2]["metadata"]["error"]
    assert not model.calls
    assert outside.read_bytes() == image_bytes()


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_image_rejects_resource_symlink_outside_workspace(routed, auto_resource_env, tmp_path):
    """An escaping resource symlink fails without weakening other containment tests."""
    env = auto_resource_env
    outside = write_binary(tmp_path / "outside.png", image_bytes())
    external_link = env.workspace / "resource/2026-01-01/external.png"
    external_link.parent.mkdir(parents=True, exist_ok=True)
    try:
        external_link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    model = FakeVisionModel(caption_json("unsafe", "Unsafe", "Must not be read."))
    response = await env.run(
        env.processor(model, routed=routed),
        [{"change": "added", "path": str(external_link)}],
    )

    result = response.metadata["results"][0]
    assert response.success is False
    assert result["metadata"]["action"] == "failed"
    assert result["metadata"]["modified"] is False
    assert "must stay inside the workspace" in result["metadata"]["error"]
    assert not model.calls
    assert outside.read_bytes() == image_bytes()


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_image_internal_symlink_keeps_logical_provenance(routed, auto_resource_env):
    """An internal symlink is read safely while ownership follows the watched alias."""
    env = auto_resource_env
    target = env.write_binary("resource/2026-01-01/original.png", image_bytes())
    link = target.with_name("alias.png")
    try:
        link.symlink_to(target.name)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    model = FakeVisionModel(caption_json("linked-image", "Linked", "An internal linked image."))
    step = env.processor(model, routed=routed)
    response = await env.run(step, [{"change": "added", "path": str(link)}])

    note_path = env.workspace / "daily/2026-01-01/linked-image.md"
    post = frontmatter.loads(note_path.read_text(encoding="utf-8"))
    assert response.success is True
    assert post.metadata["source_resource"] == "[[resource/2026-01-01/alias.png]]"
    assert "![[resource/2026-01-01/alias.png]]" in post.content
    assert len(model.calls) == 1

    link.unlink()
    deleted = await env.run(step, [{"change": "deleted", "path": str(link)}])
    assert deleted.success is True
    assert deleted.metadata["results"][0]["metadata"]["action"] == "deleted"
    assert not note_path.exists()
    assert target.is_file()


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
@pytest.mark.parametrize("existing_owner", ["different-source", "no-source"])
@pytest.mark.parametrize("change", ["modified", "deleted"])
async def test_image_preserves_unowned_same_stem_note(routed, existing_owner, change, auto_resource_env):
    """Upsert and delete never claim a same-stem note without exact ownership."""
    env = auto_resource_env
    source = env.workspace / "resource/2026-01-01/img.png"
    if change == "modified":
        write_binary(source, image_bytes())
    same_stem = env.workspace / "daily/2026-01-01/img.md"
    if existing_owner == "different-source":
        write_note(same_stem, "[[resource/2026-01-01/other.png]]", body="unrelated image note")
    else:
        same_stem.parent.mkdir(parents=True, exist_ok=True)
        same_stem.write_text(
            "---\nname: img\ndescription: user-owned note\n---\nuser-owned bytes\n",
            encoding="utf-8",
        )
    before = same_stem.read_bytes()

    model = FakeVisionModel(caption_json("generated-caption", "Generated", "Generated caption."))
    response = await env.run(env.processor(model, routed=routed), [{"change": change, "path": str(source)}])

    assert response.success is True
    assert same_stem.read_bytes() == before
    if change == "deleted":
        result = response.metadata["results"][0]["metadata"]
        assert result["action"] == "skipped"
        assert result["reason"] == "resource_note_not_found"
        assert result["modified"] is False
    else:
        generated = env.workspace / "daily/2026-01-01/generated-caption.md"
        post = frontmatter.loads(generated.read_text(encoding="utf-8"))
        assert post.metadata["source_resource"] == "[[resource/2026-01-01/img.png]]"
        assert "Generated caption." in post.content


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
@pytest.mark.parametrize("plain_text", ["   ", "```json\n\n```"], ids=["whitespace", "empty-json-fence"])
async def test_blank_plain_caption_does_not_create_or_overwrite_note(routed, plain_text, auto_resource_env):
    """An empty structured result plus blank plain fallback leaves notes untouched."""
    env = auto_resource_env
    new_source = env.write_binary("resource/2026-01-01/blank-new.png", image_bytes())
    old_source = env.write_binary("resource/2026-01-01/blank-old.png", image_bytes())
    old_note = env.write_note(
        "daily/2026-01-01/preserved.md",
        "[[resource/2026-01-01/blank-old.png]]",
        body="caption that must survive",
    )
    before = old_note.read_bytes()
    model = StructuredVisionModel(content={}, plain_text=plain_text)
    step = env.processor(model, routed=routed)

    added = await env.run(step, [{"change": "added", "path": str(new_source)}])
    modified = await env.run(step, [{"change": "modified", "path": str(old_source)}])

    for response in (added, modified):
        result = response.metadata["results"][0]["metadata"]
        assert response.success is False
        assert result["action"] == "failed"
        assert result["modified"] is False
        assert "no usable caption" in result["error"]
    assert not (env.workspace / "daily/2026-01-01/blank-new.md").exists()
    assert old_note.read_bytes() == before
    assert len(model.structured_calls) == len(model.plain_calls) == 2


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_loose_root_image_keeps_original_daily_card_across_days(routed, auto_resource_env):
    """Later updates and deletion keep a loose resource's first daily-card ownership."""
    env = auto_resource_env
    source = env.write_binary("resource/photo.png", image_bytes(color=(200, 30, 30)))
    initial_model = FakeVisionModel(caption_json("original-card", "Original", "first-day caption"))
    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-01"):
        added = await env.run(
            env.processor(initial_model, routed=routed),
            [{"change": "added", "path": str(source)}],
        )

    owned_note = env.workspace / "daily/2026-01-01/original-card.md"
    add_result = added.metadata["results"][0]["metadata"]
    assert added.success is True
    assert add_result["path"] == "daily/2026-01-01/original-card.md"
    assert add_result["action"] == "added"
    assert add_result["index"]["date"] == "2026-01-01"
    assert "first-day caption" in owned_note.read_text(encoding="utf-8")

    unrelated_note = env.write_note(
        "daily/2026-01-02/photo.md",
        "[[resource/other.png]]",
        body="unrelated note that must survive",
    )
    unrelated_before = unrelated_note.read_bytes()

    first_model = FakeVisionModel(caption_json("renamed-on-day-two", "Updated", "second-day caption"))
    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-02"):
        first_update = await env.run(
            env.processor(first_model, routed=routed),
            [{"change": "modified", "path": str(source)}],
        )

    first_result = first_update.metadata["results"][0]["metadata"]
    assert first_update.success is True
    assert first_result["path"] == "daily/2026-01-01/original-card.md"
    assert first_result["action"] == "modified"
    assert first_result["created"] is False
    assert first_result["index"]["date"] == "2026-01-01"
    assert "second-day caption" in owned_note.read_text(encoding="utf-8")
    assert not (env.workspace / "daily/2026-01-02/renamed-on-day-two.md").exists()
    assert unrelated_note.read_bytes() == unrelated_before
    assert not (env.workspace / "daily/2026-01-02.md").exists()

    source.write_bytes(image_bytes(color=(20, 90, 200)))
    second_model = FakeVisionModel(caption_json("renamed-on-day-three", "Updated again", "third-day caption"))
    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-03"):
        second_update = await env.run(
            env.processor(second_model, routed=routed),
            [{"change": "modified", "path": str(source)}],
        )

    second_result = second_update.metadata["results"][0]["metadata"]
    assert second_update.success is True
    assert second_result["path"] == "daily/2026-01-01/original-card.md"
    assert second_result["action"] == "modified"
    assert second_result["created"] is False
    assert second_result["index"]["date"] == "2026-01-01"
    assert "third-day caption" in owned_note.read_text(encoding="utf-8")
    assert not (env.workspace / "daily/2026-01-03/renamed-on-day-three.md").exists()
    assert unrelated_note.read_bytes() == unrelated_before
    assert not (env.workspace / "daily/2026-01-03.md").exists()

    source.unlink()
    delete_model = FakeVisionModel(caption_json("unused", "Unused", "Must not be requested."))
    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-04"):
        deleted = await env.run(
            env.processor(delete_model, routed=routed),
            [{"change": "deleted", "path": str(source)}],
        )

    delete_result = deleted.metadata["results"][0]["metadata"]
    assert deleted.success is True
    assert delete_result["path"] == "daily/2026-01-01/original-card.md"
    assert delete_result["action"] == "deleted"
    assert delete_result["modified"] is True
    assert delete_result["index"]["date"] == "2026-01-01"
    assert delete_result["index"]["notes"] == []
    assert not owned_note.exists()
    assert unrelated_note.read_bytes() == unrelated_before
    assert "(none)" in (env.workspace / "daily/2026-01-01.md").read_text(encoding="utf-8")
    assert not (env.workspace / "daily/2026-01-04.md").exists()
    assert len(initial_model.calls) == len(first_model.calls) == len(second_model.calls) == 1
    assert not delete_model.calls


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_loose_root_image_duplicate_daily_owners_fail_closed(routed, auto_resource_env):
    """Ambiguous exact ownership is reported without reading the image model or changing notes."""
    env = auto_resource_env
    source = env.write_binary("resource/duplicate.png", image_bytes())
    first_note = env.write_note("daily/2026-01-01/first.md", "[[resource/duplicate.png]]", body="first owner")
    second_note = env.write_note("daily/2026-01-02/second.md", "[[resource/duplicate.png]]", body="second owner")
    before = {first_note: first_note.read_bytes(), second_note: second_note.read_bytes()}
    model = FakeVisionModel(caption_json("replacement", "Replacement", "Must not be generated."))

    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-03"):
        response = await env.run(
            env.processor(model, routed=routed),
            [{"change": "modified", "path": str(source)}],
        )

    result = response.metadata["results"][0]["metadata"]
    assert response.success is False
    assert result["action"] == "failed"
    assert result["modified"] is False
    assert "Multiple daily resource notes claim resource/duplicate.png" in result["error"]
    assert "daily/2026-01-01/first.md" in result["error"]
    assert "daily/2026-01-02/second.md" in result["error"]
    assert not model.calls
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert not (env.workspace / "daily/2026-01-01.md").exists()
    assert not (env.workspace / "daily/2026-01-02.md").exists()
    assert not (env.workspace / "daily/2026-01-03.md").exists()
