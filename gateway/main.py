import logging
import os
from contextlib import asynccontextmanager

from matplotlib import image

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

#Trition
TRITON_URL = "http://triton:8000"
TRITON_MODEL = "resnet50"


@app.post("/v1/resnet50")
async def resnet50(file: UploadFile = File(...)):
    # ---------------------------------------------------------
    # 1. Validate image
    # ---------------------------------------------------------

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image.",
        )

    # ---------------------------------------------------------
    # 2. Read uploaded image
    # ---------------------------------------------------------

    image_bytes = await file.read()

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid image file.",
        ) from exc

    # ---------------------------------------------------------
    # 3. ResNet-50 preprocessing
    # ---------------------------------------------------------

    image = image.resize((256, 256))

    width, height = image.size

    left = (width - 224) // 2
    top = (height - 224) // 2
    right = left + 224
    bottom = top + 224

    image = image.crop((left, top, right, bottom))

    image = np.asarray(image, dtype=np.float32)

    # Convert [H, W, C] -> [C, H, W]
    image = np.transpose(image, (2, 0, 1))

    # Scale [0, 255] -> [0, 1]
    image = image / 255.0

    # ImageNet normalization
    mean = np.array(
        [0.485, 0.456, 0.406],
        dtype=np.float32,
    ).reshape(3, 1, 1)

    std = np.array(
        [0.229, 0.224, 0.225],
        dtype=np.float32,
    ).reshape(3, 1, 1)

    image = (image - mean) / std

    # Add batch dimension
    image = np.expand_dims(image, axis=0)

    # Ensure contiguous FP32 memory
    image = np.ascontiguousarray(image, dtype=np.float32)

    # ---------------------------------------------------------
    # 4. Build Triton inference request
    # ---------------------------------------------------------

    request = {
        "inputs": [
            {
                "name": "input__0",
                "shape": list(image.shape),
                "datatype": "FP32",
                "data": image.flatten().tolist(),
            }
        ],
        "outputs": [
            {
                "name": "output__0",
            }
        ],
    }

    # ---------------------------------------------------------
    # 5. Call Triton
    # ---------------------------------------------------------

    url = (
        f"{TRITON_URL}/v2/models/"
        f"{TRITON_MODEL}/infer"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=request,
            )
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

    # ---------------------------------------------------------
    # 6. Extract ResNet-50 output
    # ---------------------------------------------------------

    output = result["outputs"][0]

    logits = np.asarray(
        output["data"],
        dtype=np.float32,
    )

    # ---------------------------------------------------------
    # 7. Convert logits -> probabilities
    # ---------------------------------------------------------

    exp_logits = np.exp(
        logits - np.max(logits)
    )

    probabilities = exp_logits / np.sum(exp_logits)

    # ---------------------------------------------------------
    # 8. Get top-5
    # ---------------------------------------------------------

    top5_indices = np.argsort(
        probabilities
    )[-5:][::-1]

    predictions = []

    for index in top5_indices:
        predictions.append(
            {
                "class_id": int(index),
                "probability": float(
                    probabilities[index]
                ),
            }
        )

    # ---------------------------------------------------------
    # 9. Return response
    # ---------------------------------------------------------

    return {
        "model": "resnet50",
        "filename": file.filename,
        "predictions": predictions,
    }