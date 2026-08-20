import os
import tempfile
from functools import lru_cache

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile
from faster_whisper import WhisperModel

MODEL_ID = os.getenv("MODEL_ID", "tiny")
DEVICE = os.getenv("DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")

app = FastAPI(title="Audio Inference Service", version="0.1.0")


@lru_cache(maxsize=1)
def load_model() -> WhisperModel:
    return WhisperModel(
        MODEL_ID,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
    )


@asynccontextmanager
async def lifespan(app:FastAPI):
    load_model()
    yield
    print("Text inference service shutting down")
    
app=FastAPI(lifespan=lifespan
            ,title="Audio Inference Service",
            version="0.1.0",)

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


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp:
        temp.write(await file.read())
        temp.flush()

        segments, info = load_model().transcribe(temp.name)
        text = " ".join(segment.text.strip() for segment in segments)

    return {
        "model": MODEL_ID,
        "language": info.language,
        "language_probability": info.language_probability,
        "text": text,
    }
