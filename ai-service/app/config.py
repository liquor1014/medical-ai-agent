from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore"
    )

    app_env: str = "dev"
    postgres_dsn: str = "postgresql://medical:medical123@localhost:5432/medical_ai"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "medical_docs"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "medical-docs"

    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    openai_api_key: str = ""

    # ===== 多模型路由（Day 7）=====
    # 路由格式：逗号分隔，按顺序尝试；"mock" 表示兜底假模型
    llm_route_chat: str = "deepseek,qwen,openai,mock"
    llm_route_nl2sql: str = "deepseek,qwen,openai,mock"
    llm_route_report: str = "deepseek,qwen,openai,mock"
    llm_timeout_seconds: float = 20.0
    llm_stream_idle_timeout: float = 15.0
    llm_log_to_db: bool = True

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b"


settings = Settings()
