from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_path: str = "/data/em.db"
    backup_status_path: str = "/backup-status/last.json"
    owner_id: str = "default"
    allocation_stale_days: int = 45
    one_on_one_stale_days: int = 14
    log_level: str = "INFO"


settings = Settings()
