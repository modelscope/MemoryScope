"""FileFrontMatter — parsed Markdown front matter."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SUBJECT_KEY = "subject"
LEGACY_SUBJECT_KEY = "target"
SHARED_KEY = "shared"


class FileFrontMatter(BaseModel):
    """Markdown front matter; unknown keys are preserved as extras."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="Document name")
    description: str = Field(default="", description="Document description")
    subject: str | None = Field(
        default=None,
        description="Canonical stable identity of the person, team, or project this memory is about.",
    )
    shared: bool | None = Field(
        default=None,
        description="Explicitly marks a subject-independent workspace-shared memory when true.",
    )

    @property
    def model_extra(self) -> dict[str, Any] | None:
        """Get extra fields set during validation.

        Returns:
            A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`.
        """
        return self.__pydantic_extra__


def _frontmatter_mapping(value: FileFrontMatter | Mapping | None) -> Mapping:
    if isinstance(value, FileFrontMatter):
        return value.model_dump(mode="python", exclude_none=True)
    return value if isinstance(value, Mapping) else {}


def normalized_subject(value: FileFrontMatter | Mapping | None) -> str | None:
    """Return canonical ``subject``, falling back to legacy ``target``.

    If both fields exist, ``subject`` wins. This makes migration deterministic
    and prevents an old overloaded ``target`` value from overriding the new
    canonical identity.
    """
    metadata = _frontmatter_mapping(value)
    canonical = metadata.get(SUBJECT_KEY)
    if canonical is not None and not isinstance(canonical, (dict, list, tuple, set)):
        canonical_text = str(canonical).strip()
        if canonical_text:
            return canonical_text
    legacy = metadata.get(LEGACY_SUBJECT_KEY)
    if legacy is not None and not isinstance(legacy, (dict, list, tuple, set)):
        legacy_text = str(legacy).strip()
        if legacy_text:
            return legacy_text
    return None


def is_shared_memory(value: FileFrontMatter | Mapping | None) -> bool:
    """Return whether a file explicitly opts into workspace-shared recall."""
    shared = _frontmatter_mapping(value).get(SHARED_KEY)
    return shared is True or (isinstance(shared, str) and shared.strip().casefold() == "true")


def subject_scope(value: FileFrontMatter | Mapping | None) -> dict[str, str | bool | None]:
    """Return normalized subject scope used by indexing and Dream guards."""
    return {SUBJECT_KEY: normalized_subject(value), SHARED_KEY: is_shared_memory(value)}
