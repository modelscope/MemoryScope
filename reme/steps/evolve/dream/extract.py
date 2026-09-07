"""Global dream extract step."""

import json
from pathlib import Path

import frontmatter

from ...base_step import BaseStep
from ...file_io import refresh_day_index
from .._evolve import agent_reply_result_text
from ....components import R
from ....enumeration import DreamBucketEnum
from ....schema import DreamState, is_shared_memory, normalized_subject
from .utils import (
    clean_paths,
    daily_dir,
    llm_available,
    pack_paths,
    parse_structured_reply,
    recent_dates,
    scan_day_files,
    store_state,
    today,
    workspace_dir,
)

_TOOLS = ("read",)


@R.register("dream_extract_step")
class DreamExtractStep(BaseStep):
    """Scan changed daily files and globally extract merged memory units."""

    def __init__(self, scan_days: int = 2, max_units: int = 5, **kwargs):
        super().__init__(**kwargs)
        self.scan_days = scan_days
        self.max_units = max_units
        self._path_scopes: dict[str, dict] = {}

    async def execute(self):
        assert self.context is not None
        day = today(self, str(self.context.get("date", "") or ""))
        raw_scan_days = self.context.get("scan_days", self.scan_days)
        scan_days = max(int(raw_scan_days or self.scan_days), 1)
        raw_max_units = self.context.get("max_units", self.max_units)
        max_units = max(int(raw_max_units or self.max_units), 0)
        dates = recent_dates(day, scan_days)
        hint = str(self.context.get("hint", "") or "").strip()
        daily, workspace = daily_dir(self), workspace_dir(self)
        if self.file_catalog is None:
            raise RuntimeError("dream_extract_step requires file_catalog")
        self.logger.info(
            f"[{self.name}] start date={day} dates={','.join(dates)} scan_days={scan_days} "
            f"max_units={max_units} hint={bool(hint)}",
        )
        for scan_day in dates:
            self.logger.info(f"[{self.name}] refresh index start date={scan_day} daily_dir={daily}")
            await refresh_day_index(self.file_store, scan_day, daily)
            self.logger.info(f"[{self.name}] refresh index done date={scan_day}")

        existing = self._existing(
            workspace,
            [path for scan_day in dates for path in scan_day_files(workspace, scan_day, daily)],
        )
        day_mds = {f"{daily}/{scan_day}.md" for scan_day in dates}
        day_prefixes = tuple(f"{daily}/{scan_day}/" for scan_day in dates)
        nodes = await self.file_catalog.get_nodes()
        # Older Auto Dream versions checkpointed generated interests files.
        # Remove every such watermark from the dream catalog, not only entries
        # inside the current scan window. The exposure files themselves remain
        # untouched and are owned by the proactive refresh pipeline.
        legacy_interests = sorted(
            {n.path for n in nodes if n.path.startswith(f"{daily}/") and n.path.endswith("/interests.yaml")},
        )
        indexed_all = {
            n.path: n.st_mtime
            for n in nodes
            if n.path not in legacy_interests and (n.path in day_mds or n.path.startswith(day_prefixes))
        }
        indexed = {path: mt for path, mt in indexed_all.items() if path in existing}
        changed = [rel for rel, mt in existing.items() if indexed.get(rel) != mt]
        unchanged = [rel for rel, mt in existing.items() if indexed.get(rel) == mt]
        deleted = sorted((indexed_all.keys() - set(existing)) | set(legacy_interests))
        self.logger.info(
            f"[{self.name}] scan summary existing={len(existing)} indexed={len(indexed)} "
            f"changed={len(changed)} unchanged={len(unchanged)} deleted={len(deleted)}",
        )
        if deleted:
            self.logger.info(f"[{self.name}] catalog delete start paths={len(deleted)}")
            await self.file_catalog.delete(deleted)
            self.logger.info(f"[{self.name}] catalog delete done paths={len(deleted)}")

        state = DreamState(
            date=day,
            dates=dates,
            scan_days=scan_days,
            hint=hint,
            daily_dir=daily,
            workspace=str(workspace),
            files_scanned=len(existing),
            files_unchanged=len(unchanged),
            files_changed=len(changed),
            files_deleted=len(deleted),
            changed_paths=changed,
            unchanged_paths=unchanged,
            deleted_paths=deleted,
            existing=existing,
            indexed=indexed,
        )
        if not changed:
            self.logger.info(f"[{self.name}] skip no changed input dates={','.join(dates)}")
            return self._finish(state, True, f"No changed dream input for {', '.join(dates)}")
        self._path_scopes = self._load_path_scopes(workspace, changed)
        if not llm_available(self):
            state.errors.append("no llm configured; dream extract requires an LLM")
            state.failed_paths = list(changed)
            self.logger.warning(f"[{self.name}] skip no llm changed={len(changed)}")
            return self._finish(state, False, state.errors[-1])

        self.logger.info(f"[{self.name}] agent start changed={len(changed)} dates={len(dates)}")
        raw_result, meta = "", {}
        for attempt in range(2):
            try:
                result = await self.agent_wrapper.reply(
                    self.prompt_format(
                        "extract_user_message",
                        date=day,
                        dates_json=json.dumps(dates, ensure_ascii=False, indent=2),
                        hint=hint or "(none)",
                        max_units=max_units,
                        changed_paths_json=json.dumps(changed, ensure_ascii=False, indent=2),
                        path_scopes_json=json.dumps(self._path_scopes, ensure_ascii=False, indent=2),
                        material_blob=pack_paths(workspace, changed),
                    ),
                    system_prompt=self.prompt_format(
                        "extract_system_prompt",
                        workspace_dir=str(workspace),
                        buckets=", ".join(bucket.value for bucket in DreamBucketEnum),
                        max_units=max_units,
                    ),
                    job_tools=list(_TOOLS),
                )
                self.logger.info(f"[{self.name}] agent done has_result={bool(result.get('result'))}")
                raw_result = agent_reply_result_text(result)
                meta = parse_structured_reply(raw_result)
            except Exception as e:  # noqa: BLE001
                if attempt == 0:
                    self.logger.warning(
                        f"[{self.name}] extract attempt 1 returned no usable receipt; retrying once: "
                        f"{type(e).__name__}: {e}",
                    )
                    continue
                error = f"dream extract agent failed after retry: {type(e).__name__}: {e}"
                state.errors.append(error)
                state.failed_paths = list(changed)
                self.logger.error(f"[{self.name}] {error}")
                return self._finish(state, False, error)

            units = meta.get("units") if "units" in meta else meta.get("memory_units")
            if isinstance(units, list):
                break
            if attempt == 0:
                self.logger.warning(f"[{self.name}] extract attempt 1 returned an unusable receipt; retrying once")
                continue
            # Keep the warning-only result checkpointable after one retry so a bad source cannot loop forever.
            warning = "dream extract skipped unusable agent receipt after retry; expected a units list"
            state.warnings.append(warning)
            self.logger.warning(f"[{self.name}] {warning}")

        self.logger.info(f"[{self.name}] parse done keys={','.join(sorted(meta.keys())) if meta else '(none)'}")
        self.clean_output(state, meta, max_units=max_units)
        state.extract_summary = raw_result
        answer = f"Extracted {len(state.units)} unit(s) from {len(changed)} changed file(s) across {len(dates)} day(s)"
        return self._finish(state, True, answer)

    def _existing(self, workspace, files: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for rel in files:
            try:
                out[rel] = (workspace / rel).stat().st_mtime
            except OSError as e:
                self.logger.error(f"[{self.name}] stat failed on {rel}: {e}")
        return out

    @staticmethod
    def _load_path_scopes(workspace: Path, paths: list[str]) -> dict[str, dict]:
        """Read source scopes once; model output cannot broaden them later."""
        scopes: dict[str, dict] = {}
        for path in paths:
            try:
                post = frontmatter.loads((workspace / path).read_text(encoding="utf-8"))
                scopes[path] = {
                    "subject": normalized_subject(post.metadata),
                    "shared": is_shared_memory(post.metadata),
                }
            except (OSError, UnicodeError, ValueError):
                scopes[path] = {"subject": None, "shared": False}
        return scopes

    def clean_output(self, state: DreamState, meta: dict, max_units: int | None = None) -> None:
        """Clean up output"""
        allowed = set(state.changed_paths)
        for raw in meta.get("units") or meta.get("memory_units") or []:
            if max_units is not None and len(state.units) >= max_units:
                break
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            summary = str(raw.get("summary") or "").strip()
            raw_bucket = str(raw.get("bucket") or "").strip()
            paths = clean_paths(raw.get("paths"), allowed)
            if not name or not summary or not paths:
                continue
            source_scopes = [self._path_scopes[path] for path in paths if path in self._path_scopes]
            source_subjects = {scope["subject"] for scope in source_scopes if scope.get("subject")}
            if len(source_subjects) > 1:
                self.logger.warning(
                    f"[{self.name}] unit {name!r} spans incompatible subjects; dropping merged unit",
                )
                state.warnings.append(f"unit {name!r} dropped because its source paths have different subjects")
                continue
            subject = next(iter(source_subjects), None)
            shared = bool(source_scopes) and any(scope.get("shared") for scope in source_scopes) and not subject
            if not source_scopes:
                subject = normalized_subject({"subject": raw.get("subject")})
                shared = bool(raw.get("shared")) and not subject
            try:
                bucket = DreamBucketEnum(raw_bucket).value
            except ValueError:
                self.logger.warning(f"[{self.name}] unit {name!r} emitted bucket {raw_bucket!r}; routing to wiki")
                bucket = DreamBucketEnum.WIKI.value
            unit = {"name": name, "bucket": bucket, "summary": summary, "paths": paths}
            if subject:
                unit["subject"] = subject
            if shared:
                unit["shared"] = True
            state.units.append(unit)

    def _finish(self, state: DreamState, success: bool, answer: str):
        assert self.context is not None
        state.summary = answer
        store_state(self, state)
        self.context.response.success = success
        self.context.response.answer = answer
        self.logger.info(f"[{self.name}] finish success={success} answer={answer!r}")
        return self.context.response
