"""
Mahalliy muhitda botni Polling (so'rov yuborish) rejimi orqali ishga tushirish.
python-telegram-bot kutubxonasi yordamida yozilgan.
"""
import logging
from app.bot.dispatcher import application

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Bot polling rejimida ishga tushmoqda...")
    # Pollingni boshlash (post_init avtomatik tarzda jadvallar yaratadi va handlerlarni ulaydi)
    application.run_polling(timeout=30)


if __name__ == "__main__":
    main()
