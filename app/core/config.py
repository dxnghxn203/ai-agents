from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # AI Service
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None

    # Other AI Services (optional)
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    replicate_api_token: Optional[str] = None

    # Worker Configuration
    worker_concurrency: Optional[int] = None
    worker_loglevel: Optional[str] = None
    worker_queue: Optional[str] = None
    sse_timeout: Optional[int] = None

    # App Configuration
    debug: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None

    # CORS Configuration
    cors_origins: Optional[List[str]] = None

    # File Storage
    templates_dir: Optional[str] = None
    upload_dir: Optional[str] = None
    output_dir: Optional[str] = None

    # Video Settings
    max_video_duration: Optional[int] = None
    max_file_size: Optional[int] = None

    # Logging
    log_level: Optional[str] = None

    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_backend: str = "redis://localhost:6379/0"

    # Storage
    s3_bucket_name: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # App
    tmp_dir: str = "tmp"
    max_video_duration: int = 60  # seconds
    max_input_images: int = 10

    # Lottie Generator Settings
    max_file_size: int = 16 * 1024 * 1024  # 16MB
    upload_dir: str = "uploads"
    output_dir: str = "output"
    template_dir: str = "templates/lottie_samples"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }

settings = Settings()