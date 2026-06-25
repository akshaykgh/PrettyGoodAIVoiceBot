from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_from_number: str = Field(default="")
    public_base_url: HttpUrl | None = None

    openai_api_key: str = Field(default="")
    openai_realtime_model: str = "gpt-realtime-2"
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"

    target_number: str = "+18054398008"
    call_timeout_seconds: int = 210
    artifacts_dir: Path = Path("artifacts")
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    @property
    def normalized_target_number(self) -> str:
        return self.target_number.replace("-", "").replace(" ", "")

    @property
    def base_url(self) -> str:
        if self.public_base_url is None:
            raise ValueError("PUBLIC_BASE_URL is required for Twilio webhooks")
        return str(self.public_base_url).rstrip("/")

    @property
    def websocket_base_url(self) -> str:
        base = self.base_url
        if base.startswith("https://"):
            return "wss://" + base.removeprefix("https://")
        if base.startswith("http://"):
            return "ws://" + base.removeprefix("http://")
        raise ValueError("PUBLIC_BASE_URL must start with http:// or https://")

    def require_twilio(self) -> None:
        missing = [
            name
            for name, value in {
                "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
                "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
                "TWILIO_FROM_NUMBER": self.twilio_from_number,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required Twilio settings: {', '.join(missing)}")

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY")


settings = Settings()
