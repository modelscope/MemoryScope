"""Temporary session image inputs; no resource writes or transcript changes."""

import base64
from collections.abc import Callable
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import aiofiles
import httpx
from agentscope.agent import ContextConfig
from agentscope.message import Base64Source, DataBlock, Msg, TextBlock, UserMsg

from ._image_caption import DEFAULT_MAX_IMAGE_INPUT_BYTES, _build_image_request_payload
from ..file_io._path import _check_path_permission, resolve_path
from ...components.agent_wrapper.as_agent_wrapper import AsAgentWrapper
from ...enumeration import ComponentEnum


async def prepare_direct_message(
    step,
    messages: list[Msg],
    render_prompt: Callable[[list[Msg]], str],
    reply_kwargs: dict | None = None,
) -> Msg | None:
    """Interleave images with the existing rendered history and memory prompt.

    Use shared bounded source loading and provider preprocessing, retaining image
    data instead of introducing a model-generated description.
    No memory Agent has run yet, so preparation failures can safely fall back.
    """
    wrapper = step.agent_wrapper
    if not isinstance(wrapper, AsAgentWrapper):
        raise NotImplementedError("Direct images require the AgentScope wrapper")
    images = [
        (message_index, block_index, block)
        for message_index, message in enumerate(messages)
        for block_index, block in enumerate(message.content)
        if block.type == "data" and block.source.media_type.startswith("image/")
    ]
    metadata = {"mode": "direct", "status": "skipped", "image_count": len(images), "captioned_images": 0}
    step.context.response.metadata["auto_memory_images"] = metadata
    if not images:
        return None
    if not step.context.get("supports_vision", step.kwargs.get("supports_vision", False)):
        metadata.update(status="fallback", reason="supports_vision=false")
        step.logger.warning(
            f"[{step.name}] supports_vision is false; continuing with text-only memory without reading images.",
        )
        return None
    stage = "model"
    try:
        component = wrapper.as_llm
        if step.app_context is not None:
            component = step.app_context.components.get(ComponentEnum.AS_LLM, {}).get("vision", component)
        model = component.model if component is not None else None
        if model is None:
            raise ValueError("Direct images require a started memory model")
        stage = "context-image-limit"
        context_config = dict(
            (reply_kwargs or {}).get("context_config", wrapper.kwargs.get("context_config")) or {},
        )
        if "max_image_num" not in context_config:
            context_config["max_image_num"] = max(ContextConfig().max_image_num, len(images))
        if ContextConfig(**context_config).max_image_num < len(images):
            raise ValueError("The configured image limit would drop session images")
        prepared = [message.model_copy(deep=True) for message in messages]
        image_blocks: dict[str, DataBlock] = {}
        marker_prefix = f"__reme_image_{uuid4().hex}_"
        for number, (message_index, block_index, block) in enumerate(images, 1):
            stage = "source"
            data = await _image_bytes(step, block.source)
            stage = "decode"
            payload = _build_image_request_payload(data, "")
            marker = f"{marker_prefix}{number}__"
            prepared[message_index].content[block_index] = TextBlock(text=marker)
            image_blocks[marker] = block.model_copy(
                deep=True,
                update={"source": Base64Source(data=payload["data_b64"], media_type=payload["mime"])},
            )
        # Reuse string templates and history hooks (including source line numbers),
        # then remove every private marker before the model sees the message.
        stage = "prompt"
        prompt = render_prompt(prepared)
        parts = re.split("(" + "|".join(map(re.escape, image_blocks)) + ")", prompt)
        if [part for part in parts if part in image_blocks] != list(image_blocks):
            raise ValueError("Memory prompt must preserve every image once in conversation order")
        result = UserMsg(
            name="user",
            content=[image_blocks[part] if part in image_blocks else TextBlock(text=part) for part in parts if part],
        )
    except Exception as exc:  # pylint: disable=broad-except
        reason = f"{stage}: {type(exc).__name__}"
        metadata.update(status="fallback", reason=reason)
        step.logger.warning(
            f"[{step.name}] Direct image preparation failed ({reason}); continuing with text-only memory.",
        )
        return None
    if reply_kwargs is not None:
        reply_kwargs["context_config"] = context_config
        # Override only this Agent invocation; never rebind the shared wrapper.
        reply_kwargs["_model"] = model
    metadata["status"] = "prepared"
    return result


def _workspace_path(step, path: str) -> Path:
    workspace = step.file_store.workspace_path.resolve()
    target, error = resolve_path(workspace, path)
    if error or target is None:
        raise ValueError("Image path must stay inside the workspace")
    if not _check_path_permission(workspace, target, step.context.get("_allowed_paths")):
        raise PermissionError("Image path is outside the allowed paths")
    return target


async def _read_bytes(path: Path, limit: int) -> bytes:
    async with aiofiles.open(path, "rb") as stream:
        data = await stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Image exceeds the byte limit")
    return data


async def _image_bytes(step, source) -> bytes:
    limit = DEFAULT_MAX_IMAGE_INPUT_BYTES
    if source.type == "base64":
        if len(source.data) > 4 * ((limit + 2) // 3):
            raise ValueError("Image exceeds the byte limit")
        data = base64.b64decode(source.data, validate=True)
    else:
        url = urlsplit(str(source.url))
        if url.scheme == "file" and url.netloc in ("", "localhost") and not url.query and not url.fragment:
            data = await _read_bytes(_workspace_path(step, unquote(url.path)), limit)
        elif url.scheme in ("http", "https"):
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, max_redirects=3) as client:
                async with client.stream("GET", str(source.url)) as response:
                    response.raise_for_status()
                    buffer = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(buffer) + len(chunk) > limit:
                            raise ValueError("Image exceeds the byte limit")
                        buffer.extend(chunk)
                    data = bytes(buffer)
        else:
            raise ValueError("Image source must be Base64, HTTP(S), or a workspace file URI")
    if not data or len(data) > limit:
        raise ValueError("Image is empty or exceeds the byte limit")
    return data
