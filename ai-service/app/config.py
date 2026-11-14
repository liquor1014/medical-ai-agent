from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore"
    )

    app_env: str = "dev"
    postgres_dsn: str = "postgresql://medical:medical123@localhost:5432/medical_ai"

    # ===== Qdrant 向量库 =====
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "medical_docs"
    qdrant_timeout: float = 5.0          # 单次请求超时（秒）
    qdrant_retries: int = 2              # 连接失败重试次数（除首次外）
    qdrant_embedding_dim: int = 384      # 默认 all-MiniLM-L6-v2 输出维度；实际以 ensure_collection(dim) 推断为准

    # ===== Embedding 模型 =====
    # 可选："sentence_transformers"（本地）、"mock"（返回随机向量，用于无模型环境）
    embedding_backend: str = "sentence_transformers"
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # ===== Redis =====
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
