"""Shared watch-rule logic for init_changes and watch_changes steps."""

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING

from ._source_format import normalize_posix_path

if TYPE_CHECKING:
    from ...schema import ApplicationConfig
    from ...components.runtime_context import RuntimeContext


@dataclass
class WatchRule:
    """A single directory-monitoring rule."""

    path: Path
    suffixes: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


def build_watch_rules(
    app_config: "ApplicationConfig",
    workspace_path: Path,
    *,
    watch_dirs: list[str],
    watch_suffixes: list[str],
    watch_exclude_patterns: list[str] | None = None,
) -> list[WatchRule]:
    """Build rules; exclusions are case-sensitive fnmatch globs relative to each watch root.

    Paths use POSIX separators. ``*`` can match separators, as in ``fnmatch``;
    ``*/_session_images/*`` excludes session attachments below any date directory.
    """
    patterns = watch_exclude_patterns if watch_exclude_patterns is not None else []
    if not isinstance(patterns, list) or any(
        not isinstance(pattern, str) or not pattern or pattern.startswith("/") or "\\" in pattern
        for pattern in patterns
    ):
        raise ValueError("watch_exclude_patterns must be a list of relative POSIX glob strings")
    rules: list[WatchRule] = []
    for dir_field in watch_dirs:
        literal_path = Path(dir_field)
        if literal_path.is_absolute():
            rule_path = literal_path
        else:
            config_field, separator, child_path = dir_field.partition("/")
            dir_value = getattr(app_config, config_field, config_field)
            if hasattr(app_config, config_field) and dir_value in (None, ""):
                dir_value = getattr(type(app_config)(), config_field)
            if separator:
                dir_value = normalize_posix_path(f"{dir_value}/{child_path}")
            dir_name = Path(dir_value)
            rule_path = dir_name if dir_name.is_absolute() else workspace_path / dir_name
        rules.append(WatchRule(path=rule_path, suffixes=list(watch_suffixes), exclude_patterns=list(patterns)))
    return rules


def build_context_watch_rules(
    app_config: "ApplicationConfig | None",
    workspace_path: Path,
    context: "RuntimeContext",
) -> list[WatchRule]:
    """Build watch rules from context-level directories, suffixes, and exclusions."""
    if app_config is None:
        return []
    watch_dirs: list[str] = context.get("watch_dirs", [])
    watch_suffixes: list[str] = context.get("watch_suffixes", [])
    if not watch_dirs:
        return []
    return build_watch_rules(
        app_config,
        workspace_path,
        watch_dirs=watch_dirs,
        watch_suffixes=watch_suffixes,
        watch_exclude_patterns=context.get("watch_exclude_patterns", []),
    )


def collect_existing(rules: list[WatchRule], recursive: bool) -> dict[str, float]:
    """Walk rule paths and return {abs_path: st_mtime} for matching files."""
    existing: dict[str, float] = {}
    for rule in rules:
        if not rule.path.exists():
            continue
        candidates = rule.path.rglob("*") if recursive else rule.path.iterdir()
        for p in candidates:
            if not p.is_file():
                continue
            if not _match_rule(p, rule):
                continue
            abs_p = p.absolute()
            existing[str(abs_p)] = abs_p.stat().st_mtime
    return existing


def match_file(file_path: str, rules: list[WatchRule]) -> bool:
    """Return True if a file path matches any of the watch rules."""
    p = Path(file_path)
    for rule in rules:
        try:
            p.relative_to(rule.path)
        except ValueError:
            continue
        if _match_rule(p, rule):
            return True
    return False


def _match_rule(p: Path, rule: WatchRule) -> bool:
    """Apply identical suffix and exclusion rules to initial scans and live changes."""
    filename = p.name.casefold()
    if rule.suffixes and not any(filename.endswith("." + suffix.strip(".").casefold()) for suffix in rule.suffixes):
        return False
    return not _matches_exclusion(p, rule)


def _matches_exclusion(path: Path, rule: WatchRule) -> bool:
    """Match exclusions even for deleted files; no filesystem lookup is needed."""
    if not rule.exclude_patterns:
        return False
    try:
        relative = path.relative_to(rule.path).as_posix()
    except ValueError:
        return False
    return any(fnmatchcase(relative, pattern) for pattern in rule.exclude_patterns)


def is_excluded_file(file_path: str, rules: list[WatchRule]) -> bool:
    """Ignore excluded catalog entries, unless another overlapping rule includes them."""
    path = Path(file_path)
    return any(_matches_exclusion(path, rule) for rule in rules) and not match_file(file_path, rules)
