import logging

from fastapi import FastAPI

from app.config import settings
from app.routers.chat import router as chat_router
from app.routers.models import router as models_router
from app.routers.parse import router as parse_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Medical AI Service", version="0.1.0")
app.include_router(parse_router)
app.include_router(chat_router)
app.include_router(models_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ai-service", "env": settings.app_env}
