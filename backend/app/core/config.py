from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from the environment and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./inventory.db"
    cors_origins: str = "http://127.0.0.1:43123,http://localhost:43123"
    api_host: str = "0.0.0.0"
    api_port: int = 43124
    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    llm_provider: str = "fake"
    llm_model: str = "fake-model"
    llm_timeout_seconds: float = 30
    llm_max_retries: int = 3
    llm_budget_requests_per_business_per_day: int = 200
    llm_budget_tokens_per_business_per_day: int = 200000
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    orchestrator_max_steps: int = 12
    orchestrator_step_timeout_seconds: float = 15
    orchestrator_step_retries: int = 1
    orchestrator_max_concurrent_runs_per_user: int = 2
    orchestrator_rate_limit_per_user_per_minute: int = 20
    orchestrator_confidence_min: float = 0.7
    orchestrator_chat_history: int = 6
    job_secret: str | None = None
    exception_scan_scheduler_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
