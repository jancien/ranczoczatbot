from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_temperature: float = 0.3
    groq_max_tokens: int = 1024
    groq_top_p: float = 0.9

    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-4-lite"
    jina_api_key: str = ""
    jina_embedding_model: str = "jina-embeddings-v5-text-small"

    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    faiss_bucket: str = "faiss-index"

    admin_password: str = "admin"
    port: int = 8080

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
