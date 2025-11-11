"""Tests to verify package upgrades are successful."""

import pytest
import litellm
import openai
from importlib.metadata import version as get_version


def test_litellm_version():
    """Verify litellm version is upgraded."""
    version = get_version("litellm")
    major, minor = map(int, version.split('.')[:2])
    assert major >= 1 and minor >= 50, f"litellm version too old: {version}"


def test_openai_version():
    """Verify openai version is upgraded."""
    version = openai.__version__
    major, minor = map(int, version.split('.')[:2])
    assert major >= 1 and minor >= 50, f"openai version too old: {version}"


@pytest.mark.asyncio
async def test_litellm_async_still_works():
    """Verify litellm async patterns unchanged."""
    # This should not raise ImportError or AttributeError
    assert hasattr(litellm, 'acompletion')
    assert callable(litellm.acompletion)

