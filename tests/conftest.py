"""Shared pytest fixtures for the TikTok SDK test suite."""

from __future__ import annotations

import pytest
import pytest_asyncio

from tiktok.client import TikTokClient
from tiktok.http.session import TikTokSession

FAKE_TOKEN = "act.test_access_token_1234567890"


@pytest.fixture
def access_token() -> str:
    return FAKE_TOKEN


@pytest.fixture
def session(access_token: str) -> TikTokSession:
    return TikTokSession(access_token=access_token)


@pytest_asyncio.fixture
async def client(access_token: str) -> TikTokClient:  # type: ignore[misc]
    async with TikTokClient(access_token=access_token) as c:
        yield c
