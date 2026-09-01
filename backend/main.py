"""
AI Teacher — FastAPI entrypoint.

    uvicorn main:app --reload --port 8000
    docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import lesson, teach, upload, voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ai-teacher")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Teacher API",
        version="1.0.0",
        description=(
            "A human-like AI educator: Understand -> Plan -> Explain -> Question "
            "-> Evaluate -> Adapt -> Assess -> Report, grounded in uploaded "
            "material via RAG and voiced with Edge-TTS."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload.router)
    app.include_router(lesson.router)
    app.include_router(teach.router)
    app.include_router(voice.router)

    @app.get("/api/health", tags=["meta"])
    async def health() -> dict:
        return {
            "ok": True,
            "groq_key_loaded": bool(settings.groq_api_key),
            "teach_model": settings.groq_model_teach,
            "fast_model": settings.groq_model_fast,
            "embeddings": settings.embedding_model,
            "chroma_dir": str(settings.chroma_path),
        }

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal error", "hint": str(exc)[:300]},
        )

    @app.on_event("startup")
    async def startup() -> None:
        if not settings.groq_api_key:
            log.warning("GROQ_API_KEY is empty — copy .env.example to .env and add your key")
        log.info("AI Teacher API ready on model=%s", settings.groq_model_teach)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
