"""Image capability declarations belong to ReMe, not provider constructor kwargs."""

# pylint: disable=missing-function-docstring

import pytest

from reme.components.as_llm import BaseAsLLM


class _Model:
    """Observe provider construction without importing or calling an API client."""

    class Parameters:
        """Keep provider parameters visible to the assertion."""

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def __init__(self, credential, parameters=None, **kwargs):
        self.credential = credential
        self.parameters = parameters
        self.kwargs = kwargs


class _Credential:
    """Select a fake provider using the normal component startup contract."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @staticmethod
    def get_chat_model_class():
        return _Model


class _LLM(BaseAsLLM):
    """Test component preserving normal BaseAsLLM startup."""

    credential_cls = _Credential


@pytest.mark.parametrize("value", ["true", "false", 0, 1, [], {}, "", 0.0])
def test_supports_images_rejects_coercion(value):
    with pytest.raises(ValueError, match="supports_images must be a boolean or null"):
        _LLM(supports_images=value)


@pytest.mark.asyncio
@pytest.mark.parametrize("supports_images", [None, False, True])
async def test_supports_images_is_not_forwarded_to_the_provider(supports_images):
    component = _LLM(
        supports_images=supports_images,
        model="custom-deployment",
        credential={"token": "test"},
        parameters={"temperature": 0.5},
        context_size=4096,
    )
    assert component.supports_images is supports_images
    assert "supports_images" not in component.kwargs

    await component.start()
    try:
        assert component.model.kwargs == {"model": "custom-deployment", "context_size": 4096}
        assert component.model.parameters.kwargs == {"temperature": 0.5}
        assert component.model.credential.kwargs == {"token": "test"}
        previous = component.model
        await component.start()
        assert component.model is previous
    finally:
        await component.close()
