from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Tempos API"
    API_V1_PREFIX: str = "/api/v1"

    # LLM providers
    LLM_PROVIDER: str = "ollama"  # or "openai"
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "gemma:2b"
    OPENAI_API_KEY: str = ""

    # DB
    DATABASE_URL: str = "sqlite:///./data/tempos.db"

    class Config:
        env_file = ".env"

settings = Settings()
