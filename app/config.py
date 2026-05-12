from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama
    ollama_host: str = "http://localhost:11434"
    gemma_model: str = "gemma4"

    # gTTS
    gtts_lang: str = "bn"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    log_level: str = "info"

    # Rate limiting (slowapi syntax)
    rate_limit: str = "30/minute"

    # In-memory cache size (number of unique normalised texts to cache)
    cache_maxsize: int = 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
