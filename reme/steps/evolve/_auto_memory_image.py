"""Temporary session image inputs; no resource writes or transcript changes."""

import base64
from pathlib import Path
from urllib.parse import unquote, urlsplit

import aiofiles
import httpx
from agentscope.agent import ContextConfig
from agentscope.message import Base64Source, DataBlock, Msg, TextBlock

from ._image_caption import (
    DEFAULT_MAX_IMAGE_INPUT_BYTES,
    _build_image_request_payload,
    generate_image_caption,
    resolve_vision_model,
)
from ..file_io._path import _check_path_permission, resolve_path
from ...components.agent_wrapper.as_agent_wrapper import AsAgentWrapper
from ...components.prompt_handler import PromptHandler
from ...enumeration import ComponentEnum


async def prepare_direct_messages(
    step,
    messages: list[Msg],
    reply_kwargs: dict | None = None,
) -> tuple[list[Msg], list[TextBlock | DataBlock]]:
    """Bind image positions to attachments for one multimodal memory workflow.

    Use the same bounded source loading and provider preprocessing as captions,
    but retain image data instead of introducing a model-generated description.
    No memory Agent has run yet, so preparation failures can safely fall back.
    """
    images = [
        (message_index, block_index, block)
        for message_index, message in enumerate(messages)
        for block_index, block in enumerate(message.content)
        if block.type == "data" and block.source.media_type.startswith("image/")
    ]
    metadata = {"mode": "direct", "status": "skipped", "image_count": len(images), "captioned_images": 0}
    step.context.response.metadata["auto_memory_images"] = metadata
    if not images:
        return messages, []
    stage = "backend"
    try:
        wrapper = step.agent_wrapper
        if not isinstance(wrapper, AsAgentWrapper):
            raise TypeError("Direct images require the AgentScope wrapper")
        stage = "model"
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
        attachments: list[TextBlock | DataBlock] = []
        for number, (message_index, block_index, block) in enumerate(images, 1):
            stage = "source"
            data = await _image_bytes(step, block.source)
            stage = "decode"
            payload = _build_image_request_payload(data, "")
            label = f"[Image {number}]"
            prepared[message_index].content[block_index] = TextBlock(text=label)
            attachments.extend(
                [
                    TextBlock(text=label),
                    block.model_copy(
                        deep=True,
                        update={"source": Base64Source(data=payload["data_b64"], media_type=payload["mime"])},
                    ),
                ],
            )
    except Exception as exc:  # pylint: disable=broad-except
        reason = f"{stage}: {type(exc).__name__}"
        metadata.update(status="fallback", reason=reason)
        step.logger.warning(
            f"[{step.name}] Direct image preparation failed ({reason}); continuing with text-only memory.",
        )
        return messages, []
    if reply_kwargs is not None:
        reply_kwargs["context_config"] = context_config
        # Override only this Agent invocation; never rebind the shared wrapper.
        reply_kwargs["_model"] = model
    metadata["status"] = "prepared"
    return prepared, attachments


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


async def prepare_image_messages(step, messages: list[Msg], day: str) -> tuple[list[Msg], bool]:
    """Caption image blocks in copies, or visibly fall back to the original input.

    Identical bytes share a caption only within this invocation. Block positions,
    not caller-supplied IDs, identify replacements. Cancellation propagates.
    """
    images = [
        (message_index, block_index, block.source)
        for message_index, message in enumerate(messages)
        for block_index, block in enumerate(message.content)
        if block.type == "data" and block.source.media_type.startswith("image/")
    ]
    metadata = {"mode": "caption-only", "status": "skipped", "image_count": len(images), "captioned_images": 0}
    step.context.response.metadata["auto_memory_images"] = metadata
    if not images:
        return messages, False

    captions: dict[bytes, str] = {}
    positions: dict[tuple[int, int], str] = {}
    stage = "model"
    try:
        model = resolve_vision_model(step)
        if model is None:
            raise ValueError("Image captioning requires a vision-capable model")
        stage = "prompt"
        prompt = PromptHandler(language=step.language).load_prompt_by_file(
            Path(__file__).with_name("auto_image_resource.yaml"),
        )
        for message_index, block_index, source in images:
            stage = "source"
            data = await _image_bytes(step, source)
            if data not in captions:
                stage = "decode"
                payload = _build_image_request_payload(data, "")
                stage = "caption"
                parsed = await generate_image_caption(
                    model,
                    payload,
                    prompt.prompt_format(
                        "user_message",
                        file_path="(inline session image; not saved)",
                        filename=f"session-image-{len(captions) + 1}",
                        stem="session-image",
                        date=day,
                    ),
                    logger=step.logger,
                    name=step.name,
                )
                captions[data] = parsed["caption"]
                metadata["captioned_images"] = len(captions)
            positions[(message_index, block_index)] = captions[data]
    except Exception as exc:  # pylint: disable=broad-except
        # URLs and provider/decoder exceptions may contain credentials or image data.
        reason = f"{stage}: {type(exc).__name__}"
        metadata.update({"status": "fallback", "reason": reason})
        step.logger.warning(
            f"[{step.name}] Image processing failed ({reason}); falling back to the original "
            f"text-only memory input for all {len(images)} image block(s)",
        )
        return messages, False

    prepared = []
    for message_index, message in enumerate(messages):
        content = [
            (
                TextBlock(
                    text=f"[Image]\nCaption (model-generated):\n{positions[(message_index, block_index)]}\n[/Image]",
                )
                if (message_index, block_index) in positions
                else block
            )
            for block_index, block in enumerate(message.content)
        ]
        prepared.append(message.model_copy(update={"content": content}))
    metadata["status"] = "completed"
    return prepared, True
