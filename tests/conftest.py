from collections.abc import AsyncGenerator
import os

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ["DEBUG"] = "false"
os.environ.setdefault(
    "PROVIDER_KEY_ENCRYPTION_SECRET",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for a test app fixture."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
