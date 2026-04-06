from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://localhost:6379"


    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()