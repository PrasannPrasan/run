from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_name: str = "Lead Enrichment"

    # Comma-separated list, e.g. "http://localhost:5173,http://127.0.0.1:5174"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_url: str = "http://127.0.0.1:5173"

    database_url: str = "sqlite:///./app.db"

    jwt_secret: str = "change-me"
    jwt_issuer: str = "lead-enrichment"
    jwt_audience: str = "lead-enrichment-ui"
    jwt_access_token_minutes: int = 120

    redis_url: str = "redis://localhost:6379/0"

    apify_token: str | None = None
    # Default actor is a low-cost Apify Store actor with a current API schema.
    # Apify API paths use "~" between owner and actor name.
    apify_actor_id: str = "anchor~linkedin-profile-enrichment"

    lusha_api_key: str | None = None
    apollo_api_key: str | None = None
    rocketreach_api_key: str | None = None
    rocketreach_base_url: str = "https://api.rocketreach.co/api/v2"

    public_webhook_base_url: str | None = None


settings = Settings()
