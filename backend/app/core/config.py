"""Application settings, read from environment variables or a .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General
    app_name: str = "Smart Tour Companion"
    environment: str = "development"
    timezone: str = "Asia/Karachi"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Set true on Vercel style hosts that sit behind one trusted proxy.
    trust_proxy: bool = False

    # Database
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "smart_tour"

    # Auth
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = 120
    refresh_token_days: int = 14
    admin_email: str = ""
    admin_password: str = ""

    # OpenAI (the only paid service)
    openai_api_key: str = ""
    openai_model: str = "gpt-6-luna"
    openai_timeout_seconds: float = 45.0
    ai_plan_max_tokens: int = 4000
    ai_chat_max_tokens: int = 1000
    ai_daily_limit_per_user: int = 30
    ai_daily_limit_global: int = 300
    plan_cache_days: int = 7

    # Free external services
    nominatim_contact_email: str = ""
    geocode_country_codes: str = "pk"
    weather_fresh_minutes: int = 30
    geocode_fresh_days: int = 30
    safety_fresh_days: int = 7
    cache_stale_grace_hours: int = 24

    # Live companion
    arrival_radius_m: float = 150.0
    min_ping_seconds: float = 5.0
    delay_threshold_min: int = 15
    shift_apply_min_change: int = 10
    drive_speed_kmh: float = 30.0
    detour_factor: float = 1.3
    live_session_hours: int = 12
    share_default_hours: int = 6
    share_max_hours: int = 24

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def user_agent(self) -> str:
        contact = self.nominatim_contact_email or "no-contact-configured"
        return f"SmartTourCompanion/1.0 (university project; contact: {contact})"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
