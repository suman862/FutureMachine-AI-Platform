import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field


MODEL_ID = os.getenv(
    "MODEL_ID",
    "Qwen/Qwen2.5-1.5B-Instruct",
)

VLLM_URL = os.getenv(
    "VLLM_URL",
    "http://vllm:8000",
)


class GenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=10000,
    )

    max_new_tokens: int = Field(
        default=128,
        ge=1,
        le=2048,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(
        base_url=VLLM_URL,
        timeout=120.0,
    )

    yield

    await app.state.client.aclose()


app = FastAPI(
    lifespan=lifespan,
    title="Text Inference Service",
    version="0.1.0",
)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {
        "status": "alive",
    }


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    try:
        response = await app.state.client.get(
            "/v1/models",
        )

        response.raise_for_status()

        return {
            "status": "ready",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "error": str(exc),
            },
        )


@app.post("/generate")
async def generate(
    request: GenerateRequest,
) -> dict:
    try:
        response = await app.state.client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [
                    {
                        "role": "user",
                        "content": request.prompt,
                    }
                ],
                "max_tokens": request.max_new_tokens,
                "temperature": 0,
            },
        )

        response.raise_for_status()

        result = response.json()

        answer = result["choices"][0]["message"]["content"]

        return {
            "model": MODEL_ID,
            "text": answer,
        }

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "vLLM returned an error",
                "status_code": exc.response.status_code,
                "response": exc.response.text,
            },
        )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Unable to connect to vLLM",
                "detail": str(exc),
            },
        )