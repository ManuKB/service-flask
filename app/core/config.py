from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "inovera-family-platform-flask"
    database_url: str = "sqlite:///./inovera.db"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    web_app_base_url: str = "*"
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@inovera.family"
    # Path to a Firebase service-account JSON file, for sending push to the
    # Android app via FCM. Empty disables Android push (web push still works).
    fcm_credentials_path: str = ""
    reminder_scheduler_interval_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    # Instantiating Settings() validates required env vars (jwt_secret_key)
    # at startup - missing values raise immediately.
    return Settings()
