import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger("gateway")

TEXT_URL = os.getenv("TEXT_SERVICE_URL", "http://text-service:8001")
VISION_URL = os.getenv("VISION_SERVICE_URL", "http://vision-service:8002")
AUDIO_URL = os.getenv("AUDIO_SERVICE_URL", "http://audio-service:8003")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT, connect=10.0))
    yield
    await client.aclose()


app = FastAPI(
    title=" Multimodal Platform",
    version="0.1.0",
    lifespan=lifespan,
)


class TextRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    max_new_tokens: int = Field(default=128, ge=1, le=2048)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}

@app.get("/health/ready")
async def ready() -> dict[str, str]:
    if client is None:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    checks = {}
    for name, url in {
        "text": TEXT_URL,
        "vision": VISION_URL,
        "audio": AUDIO_URL,
    }.items():
        try:
            response = await client.get(f"{url}/health/ready")
            checks[name] = "ready" if response.is_success else "not_ready"
        except httpx.HTTPError:
            checks[name] = "unreachable"

    if not all(v == "ready" for v in checks.values()):
        raise HTTPException(status_code=503, detail=checks)

    return {"status": "ready"}


async def _post_json(url: str, payload: dict) -> dict:
    if client is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Inference service timeout") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream inference service returned {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Inference service unavailable") from exc


@app.post("/v1/text")
async def text(request: TextRequest) -> dict:
    return await _post_json(f"{TEXT_URL}/generate", request.model_dump())


async def _post_file(
    url: str,
    upload: UploadFile,
    prompt: str | None = None,
) -> dict:
    if client is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    data = {}
    if prompt is not None:
        data["prompt"] = prompt

    content = await upload.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")

    files = {
        "file": (
            upload.filename or "upload",
            content,
            upload.content_type or "application/octet-stream",
        )
    }

    try:
        response = await client.post(url, data=data, files=files)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Inference service timeout") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Inference service unavailable") from exc


@app.post("/v1/vision")
async def vision(
    file: UploadFile = File(...),
    prompt: str = Form("Describe this image."),
) -> dict:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Expected an image")
    return await _post_file(f"{VISION_URL}/generate", file, prompt)


@app.post("/v1/audio")
async def audio(file: UploadFile = File(...)) -> dict:
    return await _post_file(f"{AUDIO_URL}/transcribe", file)
