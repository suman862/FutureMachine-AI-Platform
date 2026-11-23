import io
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image
from starlette.formparsers import MultiPartParser
from transformers import AutoModelForVision2Seq, AutoProcessor

# ---  Set global Starlette limits to 10 MB ---
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes
MultiPartParser.max_file_size = MAX_FILE_SIZE  # noqa: B010
MultiPartParser.max_part_size = MAX_FILE_SIZE  # noqa: B010

MODEL_ID = os.getenv("MODEL_ID", "HuggingFaceTB/SmolVLM-500M-Instruct")
MODEL_REVISION = "753c1752602b5e739af7a7fa6947a635051897a3"


@lru_cache(maxsize=1)
def load_model():
    processor = AutoProcessor.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
    )
    model = AutoModelForVision2Seq.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model.eval()
    return processor, model


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_model()
    yield
    print("Vision inference service shutting down")


app = FastAPI(
    lifespan=lifespan,
    title="Vision Inference Service",
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


@app.post("/generate")
async def generate(
    file: UploadFile = File(..., description="Upload an image (Max size: 10 MB)"),  # noqa: B008
    prompt: str = Form("Describe this image."),
) -> dict:
    raw = await file.read()

    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="File size exceeds the maximum allowed limit of 10 MB."
        )

    image = Image.open(io.BytesIO(raw)).convert("RGB")

    processor, model = load_model()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    prompt_text = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
    )

    inputs = processor(
        text=prompt_text,
        images=[image],
        return_tensors="pt",
    ).to(model.device)

    with torch.inference_mode():
        generated_ids = model.generate(**inputs, max_new_tokens=256)

    generated = generated_ids[:, inputs["input_ids"].shape[1] :]
    answer = processor.batch_decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )[0]

    return {"model": MODEL_ID, "text": answer}
