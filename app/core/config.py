"""
Asosiy sozlamalar va konfiguratsiya moduli.
Pydantic BaseSettings orqali .env fayldan o'qiydi.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    """Ilovaning barcha sozlamalari."""

    # Telegram Bot
    BOT_TOKEN: str
    ADMIN_IDS: str = ""  # "123,456,789" formatida

    # Ma'lumotlar bazasi
    DATABASE_URL: str = "sqlite+aiosqlite:///./vocab_bot.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Webhook
    WEBHOOK_URL: str = "https://your-domain.com"
    WEBHOOK_PATH: str = "/webhook"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def admin_ids_list(self) -> List[int]:
        """ADMIN_IDS stringini integer ro'yxatiga aylantiradi."""
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Global settings obyekti
settings = Settings()
