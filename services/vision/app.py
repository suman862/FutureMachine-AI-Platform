import io
import os
from functools import lru_cache

import torch
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image
from transformers import AutoProcessor, AutoModelForVision2Seq

MODEL_ID = os.getenv("MODEL_ID", "HuggingFaceTB/SmolVLM-500M-Instruct")

app = FastAPI(title="Vision Inference Service", version="0.1.0")


@lru_cache(maxsize=1)
def load_model():
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForVision2Seq.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model.eval()
    return processor, model


@app.on_event("startup")
def startup() -> None:
    load_model()


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
    file: UploadFile = File(...),
    prompt: str = Form("Describe this image."),
) -> dict:
    raw = await file.read()
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

    generated = generated_ids[:, inputs["input_ids"].shape[1]:]
    answer = processor.batch_decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )[0]

    return {"model": MODEL_ID, "text": answer}
