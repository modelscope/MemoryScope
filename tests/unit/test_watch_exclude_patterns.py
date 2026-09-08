"""Session attachments opt out of both resource watcher scans and live events."""

# pylint: disable=protected-access

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from watchfiles import Change

from reme.components import ApplicationContext
from reme.components.file_catalog import LocalFileCatalog
from reme.components.runtime_context import RuntimeContext
from reme.schema import ApplicationConfig, FileNode
from reme.steps.index import InitChangesStep, WatchChangesStep
from reme.steps.index._watch_rules import (
    WatchRule,
    build_context_watch_rules,
    build_watch_rules,
    collect_existing,
    is_excluded_file,
    match_file,
)

_SESSION_IMAGES = "*/_session_images/*"


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")
    return path


def test_no_exclusions_preserves_existing_watch_behavior(tmp_path):
    """Opt-out patterns have no implicit defaults in the shared watch machinery."""
    image = _write(tmp_path / "resource/2026-09-09/_session_images/image.PNG")
    rules = build_watch_rules(
        ApplicationConfig(),
        tmp_path,
        watch_dirs=["resource_dir"],
        watch_suffixes=["png"],
    )

    assert rules[0].exclude_patterns == []
    assert match_file(str(image), rules)
    assert not is_excluded_file(str(image), rules)
    assert set(collect_existing(rules, recursive=True)) == {str(image)}


@pytest.mark.parametrize("root_kind", ["default", "custom", "absolute_config", "absolute_literal"])
def test_patterns_are_relative_to_each_configured_watch_root(tmp_path, root_kind):
    """Custom resource directories do not require rewriting exclusion patterns."""
    resource_dir = "resource" if root_kind == "default" else "attachments/images"
    watch_root = tmp_path / resource_dir
    if root_kind.startswith("absolute"):
        watch_root = tmp_path / "outside-workspace"
        resource_dir = str(watch_root)
    config = ApplicationConfig(resource_dir=resource_dir)
    watch_dirs = [str(watch_root)] if root_kind == "absolute_literal" else ["resource_dir"]
    workspace = tmp_path / "workspace" if root_kind.startswith("absolute") else tmp_path
    rules = build_context_watch_rules(
        config,
        workspace,
        RuntimeContext(
            watch_dirs=watch_dirs,
            watch_suffixes=["png"],
            watch_exclude_patterns=[_SESSION_IMAGES],
        ),
    )
    excluded = _write(watch_root / "2026-09-09/_session_images/a.png")
    ordinary = _write(watch_root / "2026-09-09/uploads/a.PNG")
    similar = _write(watch_root / "2026-09-09/my_session_images/a.png")
    case_distinct = _write(watch_root / "2026-09-10/_SESSION_IMAGES/a.png")
    _write(watch_root / "2026-09-09/uploads/a.txt")

    assert rules[0].path == watch_root
    assert not match_file(str(excluded), rules)
    assert is_excluded_file(str(excluded), rules)
    assert not is_excluded_file(str(tmp_path / "unwatched/2026-09-09/_session_images/a.png"), rules)
    expected = {str(ordinary), str(similar), str(case_distinct)}
    assert set(collect_existing(rules, recursive=True)) == expected
    assert all(match_file(path, rules) for path in expected)


def test_overlapping_rule_can_explicitly_include_excluded_path(tmp_path):
    """Any matching rule can include a path, consistently for scan and catalog nodes."""
    resource = tmp_path / "resource"
    image = _write(resource / "2026-09-09/_session_images/a.png")
    rules = [
        WatchRule(resource, ["png"], [_SESSION_IMAGES]),
        WatchRule(image.parent, ["png"]),
    ]

    assert match_file(str(image), rules)
    assert not is_excluded_file(str(image), rules)
    assert set(collect_existing(rules, recursive=True)) == {str(image)}


def test_patterns_are_independent_between_rules_and_input(tmp_path):
    """Building a rule does not alias or mutate caller configuration."""
    patterns = [_SESSION_IMAGES]
    rules = build_watch_rules(
        ApplicationConfig(),
        tmp_path,
        watch_dirs=["resource_dir", "daily_dir"],
        watch_suffixes=[],
        watch_exclude_patterns=patterns,
    )
    rules[0].exclude_patterns.append("private/*")

    assert rules[1].exclude_patterns == patterns == [_SESSION_IMAGES]


@pytest.mark.parametrize("invalid", ["*.png", 7, [None], [""], ["/absolute/*"], ["windows\\*"]])
def test_invalid_exclusion_configuration_fails_explicitly(tmp_path, invalid):
    """Misconfigured strings cannot silently become a list of one-character globs."""
    with pytest.raises(ValueError, match="watch_exclude_patterns"):
        build_context_watch_rules(
            ApplicationConfig(),
            tmp_path,
            RuntimeContext(watch_dirs=["resource_dir"], watch_exclude_patterns=invalid),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("absolute_nodes", [False, True])
async def test_initial_scan_does_not_delete_excluded_catalog_resources(tmp_path, absolute_nodes):
    """Existing and already-deleted attachments are unmanaged, not deletion candidates."""
    app_context = ApplicationContext(workspace_dir=str(tmp_path))
    root = tmp_path / "resource/2026-09-09"
    image = _write(root / "_session_images/image.png")
    missing_image = root / "_session_images/missing.png"
    unchanged = _write(root / "unchanged.PNG")
    added = _write(root / "added.png")
    deleted = root / "deleted.png"
    catalog = LocalFileCatalog(name="resource", app_context=app_context)
    await catalog.start()
    try:
        nodes = [
            FileNode(
                path=str(path) if absolute_nodes else path.relative_to(tmp_path).as_posix(),
                st_mtime=path.stat().st_mtime if path.exists() else 0,
            )
            for path in (image, missing_image, unchanged, deleted)
        ]
        await catalog.upsert(nodes)
        step = InitChangesStep(monitor_type="file_catalog", file_catalog=catalog, app_context=app_context)
        context = RuntimeContext(
            watch_dirs=["resource_dir"],
            watch_suffixes=["png"],
            watch_exclude_patterns=[_SESSION_IMAGES],
        )
        response = await step(context)

        assert response.metadata["counts"] == {"added": 1, "modified": 0, "deleted": 1}
        assert {(change["change"], change["path"]) for change in context["changes"]} == {
            ("added", str(added)),
            ("deleted", str(deleted)),
        }
        assert await catalog.get_nodes() == nodes
    finally:
        await catalog.close()


@pytest.mark.asyncio
async def test_live_watcher_filters_added_modified_and_deleted_attachments(tmp_path, monkeypatch):
    """The actual awatch filter prevents all attachment events reaching downstream jobs."""
    root = tmp_path / "resource/2026-09-09"
    excluded = _write(root / "_session_images/image.png")
    excluded_deleted = root / "_session_images/deleted.png"
    added = _write(root / "ordinary.PNG")
    deleted = root / "deleted.png"
    events = {
        (Change.added, str(excluded)),
        (Change.modified, str(excluded)),
        (Change.deleted, str(excluded_deleted)),
        (Change.added, str(added)),
        (Change.deleted, str(deleted)),
    }

    async def fake_awatch(*paths, watch_filter, **_kwargs):
        assert paths == (tmp_path / "resource",)
        yield {(change, path) for change, path in events if watch_filter(change, path)}

    monkeypatch.setattr("reme.steps.index.watch_changes.awatch", fake_awatch)
    step = WatchChangesStep(app_context=ApplicationContext(workspace_dir=str(tmp_path)))
    dispatch = AsyncMock()
    monkeypatch.setattr(step, "dispatch_steps", dispatch)
    await step(
        RuntimeContext(
            stop_event=asyncio.Event(),
            watch_dirs=["resource_dir"],
            watch_suffixes=["png"],
            watch_exclude_patterns=[_SESSION_IMAGES],
        ),
    )

    dispatch.assert_awaited_once()
    changes = dispatch.call_args.kwargs["changes"]
    assert {(change["change"], change["path"]) for change in changes} == {
        ("added", str(added)),
        ("deleted", str(deleted)),
    }
