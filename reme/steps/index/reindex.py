"""Explicit scoped rebuild of source-derived search state."""

from ..base_step import BaseStep
from .init_changes import InitChangesStep
from ...components import R


@R.register("reindex_step")
class ReindexStep(BaseStep):
    """Rebuild indexes and, for ``all``, reparse workspace Markdown first."""

    async def _rescan_sources(self) -> dict:
        """Rebuild chunks from source files so frontmatter migrations repeatably apply."""
        await self.file_store.clear()
        scanner = InitChangesStep(
            app_context=self.app_context,
            monitor_type="file_store",
            monitor_name="default",
            dispatch_steps=[{"backend": "update_index_step"}],
        )
        response = await scanner(
            self.context,
            watch_dirs=["daily_dir", "digest_dir"],
            watch_suffixes=["md"],
        )
        return dict(response.metadata)

    async def execute(self):
        assert self.context is not None
        scope = str(self.context.get("scope", "all"))
        rescan_sources = bool(self.context.get("rescan_sources", self.kwargs.get("rescan_sources", True)))
        source_scan = {}
        if scope == "all" and rescan_sources and self.app_context is not None:
            source_scan = await self._rescan_sources()
        details = await self.file_store.reindex(scope)

        self.context.response.answer = details
        self.context.response.metadata.update(details)
        self.context.response.metadata["scope"] = scope
        if source_scan:
            self.context.response.metadata["source_scan"] = source_scan
        return self.context.response
