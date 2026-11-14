import logging

from fastapi import FastAPI

from app.config import settings
from app.llm.providers import llm
from app.routers.chat import router as chat_router
from app.routers.models import router as models_router
from app.routers.parse import router as parse_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Medical AI Service", version="0.1.0")
app.include_router(parse_router)
app.include_router(chat_router)
app.include_router(models_router)


@app.on_event("startup")
def load_provider_configs() -> None:
    """启动时加载页面持久化的模型提供者配置，覆盖环境变量默认值。"""
    try:
        from app.db import model_provider_store

        model_provider_store.ensure_table()
        applied = llm.apply_provider_configs(model_provider_store.list_configs())
        logger.info("模型提供者配置加载完成: %d 条", applied)
    except Exception as exc:  # 数据库不可用时不影响服务启动
        logger.warning("加载持久化模型配置失败，使用环境变量默认值: %s", exc)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ai-service", "env": settings.app_env}
