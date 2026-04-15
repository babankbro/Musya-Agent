from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "chat-aio"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"

    # MinIO
    MINIO_ENDPOINT: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "uploads"
    MINIO_USE_SSL: bool = False

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MODEL_PRO: str = "gemini-2.5-pro"
    REPORT_MAX_TOKENS: int = 8192

    # pgvector (PostgreSQL-native vector search — replaces ChromaDB)
    PGVECTOR_COLLECTION: str = "musya_documents"
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"  # Google Gemini embedding API (768-dim)

    # Document Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: str = ".pdf,.docx,.txt,.md"
    AUTO_INGEST_ON_UPLOAD: bool = True
    ALLOW_EXTERNAL_URL_IMPORT: bool = True
    EXTERNAL_URL_TIMEOUT: int = 30

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def db_dsn(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def db_dsn_async(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def minio_endpoint_url(self) -> str:
        return f"{self.MINIO_ENDPOINT}:{self.MINIO_PORT}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
