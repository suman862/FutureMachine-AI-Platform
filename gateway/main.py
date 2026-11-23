import io
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import httpx
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field

#  to allow files up to 25 MB in the gateway ---
MAX_FILE_SIZE = 25 * 1024 * 1024

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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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


async def _post_json(
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if client is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())
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
async def text(request: TextRequest) -> dict[str, Any]:
    return await _post_json(f"{TEXT_URL}/generate", request.model_dump())


async def _post_file(
    url: str,
    upload: UploadFile,
    prompt: str | None = None,
    max_size: int = MAX_FILE_SIZE,
) -> dict[str, Any]:
    if client is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    data = {}
    if prompt is not None:
        data["prompt"] = prompt

    content = await upload.read(max_size + 1)

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum allowed limit of {max_size // (1024 * 1024)} MB",
        )

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
        return cast(dict[str, Any], response.json())

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Inference service timeout",
        ) from exc

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Inference service unavailable",
        ) from exc


@app.post("/v1/vision")
async def vision(
    file: UploadFile = File(..., description="Upload an image (Max size: 10 MB)"),  # noqa: B008
    prompt: str = Form("Describe this image."),
) -> dict[str, Any]:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Expected an image")

    # Enforce 10 MB limit for vision
    return await _post_file(f"{VISION_URL}/generate", file, prompt, max_size=10 * 1024 * 1024)


@app.post("/v1/audio")
async def audio(
    file: UploadFile = File(..., description="Upload an audio file (Max size: 25 MB)"),  # noqa: B008
) -> dict[str, Any]:
    return await _post_file(f"{AUDIO_URL}/v1/audio", file)


# Trition
TRITON_URL = "http://triton:8000"
TRITON_MODEL = "resnet50"


@app.post("/v1/resnet50")
async def resnet50(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_bytes = await file.read(10 * 1024 * 1024 + 1)
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds the maximum allowed limit of 10 MB",
        )

    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid image file.",
        ) from exc

    # Resize and center crop
    pil_image = pil_image.resize((256, 256))
    width, height = pil_image.size

    left = (width - 224) // 2
    top = (height - 224) // 2

    pil_image = pil_image.crop((left, top, left + 224, top + 224))

    # Convert PIL image to NumPy array (CHW format)
    image_array = np.asarray(pil_image, dtype=np.float32)
    image_array = np.transpose(image_array, (2, 0, 1))
    image_array = image_array / 255.0

    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)

    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)

    image_array = (image_array - mean) / std
    image_array = np.expand_dims(image_array, axis=0)
    image_array = np.ascontiguousarray(image_array, dtype=np.float32)

    # Build Triton inference request
    request = {
        "inputs": [
            {
                "name": "input__0",
                "shape": list(image_array.shape),
                "datatype": "FP32",
                "data": image_array.flatten().tolist(),
            }
        ],
        "outputs": [
            {
                "name": "output__0",
            }
        ],
    }

    # Call Triton
    url = f"{TRITON_URL}/v2/models/{TRITON_MODEL}/infer"

    try:
        async with httpx.AsyncClient(timeout=30.0) as triton_client:
            response = await triton_client.post(url, json=request)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Triton: {exc}",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Triton inference failed.",
                "triton_status": response.status_code,
                "triton_response": response.text,
            },
        )

    result = response.json()
    output = result["outputs"][0]

    logits = np.asarray(output["data"], dtype=np.float32)

    # Convert logits to probabilities
    exp_logits = np.exp(logits - np.max(logits))
    probabilities = exp_logits / np.sum(exp_logits)

    # Get top-5 predictions
    top5_indices = np.argsort(probabilities)[-5:][::-1]

    predictions = [
        {
            "class_id": int(index),
            "probability": float(probabilities[index]),
        }
        for index in top5_indices
    ]

    return {
        "model": "resnet50",
        "filename": file.filename,
        "predictions": predictions,
    }
