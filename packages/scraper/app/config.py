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

    class Config:
        env_file = ".env"


settings = Settings()
