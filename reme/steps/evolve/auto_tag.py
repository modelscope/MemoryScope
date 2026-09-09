"""auto_tag — generate frontmatter tags for modified Markdown files."""

from pathlib import Path

import frontmatter

from ._evolve import agent_reply_result_text
from ..base_step import BaseStep
from ..file_io import parse_daily_date, refresh_day_index
from ..file_io._path import display_path, resolve_path
from ..index import normalize_posix_path
from ...components import R

_MAX_TAGS = 8
_MAX_TAG_LENGTH = 64


def normalize_tags(value) -> list[str]:
    """Return unique retrieval-friendly tags that satisfy the storage contract."""
    if not isinstance(value, list):
        return []

    tags: list[str] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            continue
        tag = str(item).strip()
        if not tag or len(tag) > _MAX_TAG_LENGTH:
            continue
        if any(char.isspace() for char in tag):
            continue
        if not any(char.isalnum() for char in tag):
            continue
        dedupe_key = tag.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        tags.append(tag)
        if len(tags) >= _MAX_TAGS:
            break
    return tags


@R.register("auto_tag_step")
class AutoTagStep(BaseStep):
    """Generate tags for each eligible path produced by an earlier Step."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools = ["read", "list_tags", "frontmatter_read", "frontmatter_update"]

    def _eligible_paths(self) -> tuple[list[str], list[str]]:
        assert self.context is not None
        raw_paths = self.context.get("modified_paths") or []
        if not isinstance(raw_paths, list):
            raw_paths = [raw_paths]

        workspace = Path(self.file_store.workspace_path or ".").resolve()
        eligible: list[str] = []
        ignored: list[str] = []
        seen: set[str] = set()
        for raw_path in raw_paths:
            raw = str(raw_path or "").strip()
            target, err = resolve_path(workspace, raw)
            if err or target is None or not target.is_file() or target.suffix.lower() != ".md":
                ignored.append(raw)
                continue
            path = normalize_posix_path(display_path(workspace, target))
            if path in seen:
                continue
            seen.add(path)
            eligible.append(path)
        return eligible, ignored

    async def _process_path(self, path: str, tag_key: str) -> str:
        result = await self.agent_wrapper.reply(
            self.prompt_format("user_message", path=path, tags_key=tag_key),
            system_prompt=self.prompt_format("system_prompt", tags_key=tag_key),
            job_tools=self.tools,
            injected_job_kwargs={"_allowed_paths": [path]},
        )

        target = Path(self.file_store.workspace_path or ".") / path
        metadata = dict(frontmatter.loads(target.read_text(encoding="utf-8")).metadata or {})
        normalized = normalize_tags(metadata.get(tag_key))
        if metadata.get(tag_key) != normalized:
            response = await self.run_job(
                "frontmatter_update",
                path=path,
                metadata={tag_key: normalized},
                _allowed_paths=[path],
            )
            if not response.success:
                raise RuntimeError(str(response.answer))
        return agent_reply_result_text(result)

    def _daily_date(self, path: str) -> str | None:
        daily_dir = normalize_posix_path(str(self.config_value("daily_dir"))).strip("/")
        prefix = f"{daily_dir}/"
        if not path.startswith(prefix):
            return None
        remainder = path[len(prefix) :]
        parts = remainder.split("/")
        if len(parts) != 2:
            return None
        return parse_daily_date(parts[0])

    async def execute(self):
        assert self.context is not None
        initial_success = self.context.response.success
        tag_index = getattr(self.file_store, "tag_index", None)
        if tag_index is None:
            self.context.response.success = False
            self.context.response.answer = "Error: tag index is not configured"
            return self.context.response

        eligible, ignored = self._eligible_paths()
        tagged: list[str] = []
        failed: list[dict[str, str]] = []
        summaries: list[str] = []
        dates: set[str] = set()
        for path in eligible:
            if day := self._daily_date(path):
                dates.add(day)
            try:
                summaries.append(await self._process_path(path, tag_index.tag_key))
                tagged.append(path)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                failed.append({"path": path, "error": str(exc)})
                self.logger.warning(f"[{self.name}] failed path={path}: {exc}")

        indexes = [
            await refresh_day_index(self.file_store, day, self.config_value("daily_dir")) for day in sorted(dates)
        ]
        self.context.response.success = initial_success and not failed
        if failed:
            self.context.response.answer = f"Tagged {len(tagged)} file(s); {len(failed)} failed"
        elif tagged:
            self.context.response.answer = f"Tagged {len(tagged)} file(s)"
        self.context.response.metadata["auto_tag"] = {
            "tagged_paths": tagged,
            "ignored_paths": ignored,
            "failed_paths": failed,
            "indexes": indexes,
            "summaries": [summary for summary in summaries if summary],
        }
        return self.context.response
