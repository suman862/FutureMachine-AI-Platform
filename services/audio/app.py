import os
import tempfile
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, File, HTTPException, UploadFile
from faster_whisper import WhisperModel
from starlette.formparsers import MultiPartParser

# --- 1. MUST BE SET HERE BEFORE APP CREATION ---
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB in bytes
MultiPartParser.max_file_size = MAX_FILE_SIZE  # noqa: B010
MultiPartParser.max_part_size = MAX_FILE_SIZE  # noqa: B010
# -----------------------------------------------

MODEL_ID = os.getenv("MODEL_ID", "tiny")
DEVICE = os.getenv("DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")


@lru_cache(maxsize=1)
def load_model() -> WhisperModel:
    return WhisperModel(
        MODEL_ID,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield
    print("Text inference service shutting down")


app = FastAPI(
    lifespan=lifespan,
    title="Audio Inference Service",
    version="0.1.0",
)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        load_model()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}


@app.post("/v1/audio")
async def transcribe(
    file: UploadFile = File(..., description="Upload an audio file (Max size: 25 MB)"),  # noqa: B008
) -> dict:
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size exceeds the maximum allowed limit of 25 MB.",
        )

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp:
        temp.write(contents)
        temp.flush()

        segments, info = load_model().transcribe(temp.name)
        text = " ".join(segment.text.strip() for segment in segments)

    return {
        "model": MODEL_ID,
        "language": info.language,
        "language_probability": info.language_probability,
        "text": text,
    }
