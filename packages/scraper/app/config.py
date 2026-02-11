from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://formbot:formbot@db:5432/formbot"
    ollama_url: str = "http://ollama:11434"
    encryption_key: str = ""
    vnc_enabled: bool = True
    novnc_host: str = "novnc"
    novnc_port: int = 6080
    max_concurrent_browsers: int = 5
    screenshot_dir: str = "/app/screenshots"
    upload_dir: str = "/app/uploads"

    # Pusher/Soketi config for broadcasting
    pusher_app_id: str = "100001"
    pusher_app_key: str = "formbot-key"
    pusher_app_secret: str = "formbot-secret"
    pusher_host: str = "websocket"
    pusher_port: int = 6001

    class Config:
        env_file = ".env"


settings = Settings()
