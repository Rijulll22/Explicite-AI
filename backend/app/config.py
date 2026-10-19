from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:8443"

    # Application
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"

    # Upload / analysis
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024   # 10 MB — FR-PROJ-02
    ANALYSIS_TIMEOUT_SECONDS: int = 300        # 5 min per job

    # LLM — optional; set LLM_PROVIDER to "anthropic" or "ollama" to enable
    LLM_PROVIDER: str = "none"           # "none" | "anthropic" | "ollama"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_TOKENS: int = 512            # response tokens per AI call

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
