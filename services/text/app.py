import os
from functools import lru_cache

import torch
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")

app = FastAPI(title="Text Inference Service", version="0.1.0")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    max_new_tokens: int = Field(default=128, ge=1, le=2048)


@lru_cache(maxsize=1)
def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model.eval()
    return tokenizer, model


@asynccontextmanager
async def lifespan(app:FastAPI):
    load_model()
    yield
    print("The model can produce false result. Verify with expert")
    
app=FastAPI(lifespan=lifespan
            ,title="Text Inference Service",
            version="0.1.0")

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
def generate(request: GenerateRequest) -> dict:
    tokenizer, model = load_model()
    messages = [{"role": "user", "content": request.prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=request.max_new_tokens,
            do_sample=False,
        )

    generated = output[0][inputs["input_ids"].shape[1]:]
    answer = tokenizer.decode(generated, skip_special_tokens=True)
    return {"model": MODEL_ID, "text": answer}
