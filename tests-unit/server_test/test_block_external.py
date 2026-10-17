"""The web UI is always served with a Content-Security-Policy that blocks external connections."""

from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import server


async def pong(request):
    return web.Response(text="pong")


@pytest.mark.asyncio
async def test_csp_header_always_set():
    prompt_server = server.PromptServer(None, MagicMock(enabled=False))
    prompt_server.app.router.add_get("/ping", pong)
    async with TestClient(TestServer(prompt_server.app)) as client:
        resp = await client.get("/ping")
        assert resp.status == 200
        csp = resp.headers.get("Content-Security-Policy")
    assert "connect-src 'self' data:" in csp
