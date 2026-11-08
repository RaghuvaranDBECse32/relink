from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SafeStudy-Agent V2"
    environment: str = "development"

    database_url: str = "sqlite:///./safestudy.db"
    auto_create_tables: bool = True  # dev convenience; use Alembic in production

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


    embedding_backend: str = "hash"  # "hash" | "sentence-transformers"

    enkrypt_api_key: str = ""

    cors_origins: str = "http://localhost:5173"
    max_message_chars: int = 4000
    max_upload_mb: int = 10

    @property
    def embedding_dim(self) -> int:
        # MiniLM is 384-d; the hashed lexical fallback uses a larger space to limit collisions.
        return 384 if self.embedding_backend == "sentence-transformers" else 2048

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
