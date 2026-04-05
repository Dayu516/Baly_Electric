from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---------- Database ----------
    DATABASE_URL: str = "postgresql://ottimo:ottimo@localhost:5432/ottimo"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_ECHO: bool = False

    # ---------- Auth ----------
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 hours for store use

    # ---------- Backup ----------
    BACKUP_DIR: str = "/backups"
    BACKUP_RETAIN_DAYS: int = 7

    # ---------- App ----------
    APP_NAME: str = "OTTIMO"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()  # type: ignore[call-arg]