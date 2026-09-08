"""Image resource processor for the unified auto-resource router."""

from pathlib import Path, PurePosixPath

import aiofiles
from agentscope.model import ChatModelBase

from ..file_io._path import IMAGE_SUFFIXES
from ._image_caption import (
    DEFAULT_MAX_IMAGE_INPUT_BYTES,
    DEFAULT_MAX_IMAGE_PIXELS,
    build_image_request_payload,
    generate_image_caption,
    resolve_vision_model,
)
from .base_auto_resource import _SOURCE_RESOURCE_KEY, _sanitize_note_name, BaseAutoResourceStep
from ...components import R


@R.register("auto_image_resource_step")
class AutoImageResourceStep(BaseAutoResourceStep):
    """Interpret image resource files into daily notes via a direct VLM call.

    Unlike text resources (agent + file tools), the image interpretation is a
    single vision-model call. Images larger than the request budget or in
    provider-unfriendly formats are downscaled/re-encoded in memory for the
    request only; files under ``resource/`` are never modified. Note lookup,
    renaming, deletion linkage, and day-index refresh reuse the shared
    BaseAutoResourceStep lifecycle; only the interpretation differs.
    """

    resource_suffixes = IMAGE_SUFFIXES
    router_inherit_keys = BaseAutoResourceStep.router_inherit_keys | frozenset(
        {"as_llm", "max_image_bytes", "max_image_pixels"},
    )

    def _max_image_bytes(self) -> int:
        """Return the image read limit from Step or Job context."""
        value = self.kwargs.get("max_image_bytes")
        if value is None and self.context is not None:
            value = self.context.get("max_image_bytes")
        return int(value) if value is not None else DEFAULT_MAX_IMAGE_INPUT_BYTES

    def _max_image_pixels(self) -> int:
        """Return the deployment-controlled pre-decode pixel limit."""
        value = self.kwargs.get("max_image_pixels", DEFAULT_MAX_IMAGE_PIXELS)
        try:
            limit = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max_image_pixels must be a positive integer: {value!r}") from exc
        if limit <= 0:
            raise ValueError(f"max_image_pixels must be a positive integer: {value!r}")
        return limit

    def _vision_model(self) -> ChatModelBase | None:
        """Resolve explicit ``as_llm`` through Ref, otherwise prefer vision/default."""
        return resolve_vision_model(self)

    async def _read_image(self, file_path: str, source_path: Path) -> dict | None:
        """Read the image file and build the VLM request payload.

        Returns ``None`` when the change must be skipped (stat failure or
        oversized file); the skip outcome is already recorded on the response.
        """
        max_image_bytes = self._max_image_bytes()
        try:
            size_bytes = source_path.stat().st_size
        except OSError as exc:
            self.context.response.success = False
            self.context.response.answer = f"Failed to inspect resource file: {file_path}: {exc}"
            self.context.response.metadata.update(
                {
                    "path": file_path,
                    "action": "failed",
                    "error": str(exc),
                    "modified": False,
                },
            )
            self.logger.warning(f"[{self.name}] resource stat failed file_path={file_path} error={exc}")
            return None
        if size_bytes > max_image_bytes:
            self._record_oversized_image(file_path, size_bytes, max_image_bytes)
            return None

        self.logger.info(f"[{self.name}] read image start file_path={file_path}")
        async with aiofiles.open(source_path, "rb") as f:
            data = await f.read(max_image_bytes + 1)
        if len(data) > max_image_bytes:
            self._record_oversized_image(file_path, len(data), max_image_bytes)
            return None
        payload = build_image_request_payload(
            data,
            Path(file_path).suffix.lower(),
            max_image_pixels=self._max_image_pixels(),
        )
        self.logger.info(
            f"[{self.name}] read image done file_path={file_path} size_bytes={size_bytes} "
            f"mime={payload['mime']} source_mime={payload['source_mime']} converted={payload['converted']}",
        )
        return payload

    def _record_oversized_image(self, file_path: str, size_bytes: int, max_image_bytes: int) -> None:
        """Record a stable skip response for an image over the compressed-byte limit."""
        assert self.context is not None
        self.context.response.success = True
        self.context.response.answer = (
            f"Skipped oversized image resource file: {file_path} ({size_bytes} > {max_image_bytes} bytes)"
        )
        self.context.response.metadata.update(
            {
                "path": file_path,
                "action": "skipped",
                "reason": "file_too_large",
                "oversized": True,
                "size_bytes": size_bytes,
                "max_image_bytes": max_image_bytes,
                "modified": False,
            },
        )
        self.logger.warning(
            f"[{self.name}] skip oversized image resource file_path={file_path} "
            f"size_bytes={size_bytes} max_image_bytes={max_image_bytes}",
        )

    async def _handle_upsert(
        self,
        file_path: str,
        date_str: str,
        note_stem: str,
        added: bool,
        source_path: Path,
    ) -> None:
        """Caption the image and write/refresh its note (image counterpart of the text upsert)."""
        note_state = await self._prepare_resource_note(date_str, file_path, note_stem)
        note_path = note_state.path
        self.logger.info(
            f"[{self.name}] upsert start file_path={file_path} date={date_str} " f"note_stem={note_stem} added={added}",
        )

        model = self._vision_model()
        if model is None:
            self.context.response.success = True
            self.context.response.answer = f"Skipped image resource without a vision model: {file_path}"
            self.context.response.metadata.update(
                {
                    "path": file_path,
                    "action": "skipped",
                    "reason": "vision_model_not_configured",
                    "modified": False,
                },
            )
            self.logger.warning(f"[{self.name}] no vision model configured file_path={file_path}")
            return

        payload = await self._read_image(file_path, source_path)
        if payload is None:
            return

        parsed = await generate_image_caption(
            model,
            payload,
            self.prompt_format(
                "user_message",
                file_path=file_path,
                filename=PurePosixPath(file_path).name,
                stem=note_stem,
                date=date_str,
            ),
            logger=self.logger,
            name=self.name,
        )
        name = _sanitize_note_name(str(parsed.get("name") or ""), note_stem)
        caption = str(parsed.get("caption") or "").strip()
        description = str(parsed.get("description") or "").strip() or caption[:120]
        body = f"![[{file_path}]]\n\n## Caption\n\n{caption}\n"

        # The write job's ``name`` parameter is the note name; calling the job
        # directly (instead of run_job) keeps it clear of run_job's
        # positional-only job-selector argument.
        write_job = self.get_job("write")
        if write_job is None:
            raise RuntimeError("Job write not found")
        write_response = await write_job(
            path=note_path,
            name=name,
            description=description,
            content=body,
            metadata={
                _SOURCE_RESOURCE_KEY: self._source_resource_link(file_path),
                "kind": "image",
                "media_type": payload["source_mime"],
            },
        )
        if not write_response.success:
            raise RuntimeError(f"write failed: {write_response.answer}")
        note_path = await self._finalize_resource_note(
            note_state,
            date_str,
            file_path,
            note_stem,
            added,
        )
        if note_path is None:
            raise RuntimeError(f"Image caption note was not written: {file_path}")

        self.context.response.success = True
        self.context.response.answer = f"Captioned image resource {file_path} -> {note_path}"
        self.context.response.metadata.update(
            {
                "media_type": payload["source_mime"],
            },
        )
        self.logger.info(f"[{self.name}] done {note_path} modified={self.context.response.metadata['modified']}")
