from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    secret_key: str = secrets.token_hex(32)
    debug: bool = False
    base_url: str = "http://localhost:8000"
    app_version: str = "0.1.0"

    # Database
    database_url: str = "sqlite:////data/domani.db"

    # WHOIS
    whois_timeout_seconds: int = 10
    whois_retry_count: int = 3
    whois_rate_limit_seconds: float = 2.0

    # Scheduler
    default_check_interval_hours: int = 6
    fast_poll_interval_minutes: int = 5
    expiring_soon_days: int = 30
    expiring_critical_days: int = 7

    # Email defaults (can be overridden via Settings UI)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True


settings = Settings()
