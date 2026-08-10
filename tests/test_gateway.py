import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app


@pytest.mark.asyncio
async def test_live():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_text_validation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/v1/text", json={"prompt": ""})

    assert response.status_code == 422
