from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://formbot:formbot@db:5432/formbot"
    encryption_key: str = ""
    vnc_enabled: bool = True
    novnc_host: str = "novnc"
    novnc_port: int = 6080
    max_concurrent_browsers: int = 5
    screenshot_dir: str = "/app/screenshots"
    upload_dir: str = "/app/uploads"

    # Backend callback config
    backend_url: str = "http://backend:8000"
    internal_api_key: str = "formbot-internal"

    # Pusher/Soketi config for broadcasting
    pusher_app_id: str = "100001"
    pusher_app_key: str = "formbot-key"
    pusher_app_secret: str = "formbot-secret"
    pusher_host: str = "websocket"
    pusher_port: int = 6001

    # MinIO config for screenshot storage
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "formbot"
    minio_secret_key: str = "formbot-secret-key"
    minio_bucket: str = "formbot-screenshots"

    class Config:
        env_file = ".env"


settings = Settings()
