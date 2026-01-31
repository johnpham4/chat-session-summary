from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    OPENAI_API_KEY: str | None = None
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/chat_db"

    MAX_CONTEXT_MESSAGES: int = 12
    TOKEN_THRESHOLD: int = 3000
    KEEP_RECENT: int = 3

settings = Settings()