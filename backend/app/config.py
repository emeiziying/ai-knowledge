import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    debug: bool = False
    
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/ai_knowledge_base"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "documents"
    
    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # AI Services
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    
    class Config:
        env_file = ".env"

settings = Settings()