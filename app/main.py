"""
FastAPI dasturi va Webhook ulanish nuqtasi.
python-telegram-bot kutubxonasi yordamida yozilgan.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from telegram import Update

from app.core.config import settings
from app.bot.dispatcher import application

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ FastAPI ishga tushishi va to'xtashi jarayonlari. """
    # 1. PTB Application-ni initsializatsiya qilish (post_init ishga tushadi)
    await application.initialize()
    await application.start()

    # 2. Webhook sozlash (agar sozlangan bo'lsa)
    webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}{settings.WEBHOOK_PATH}"
    logger.info(f"Webhook o'rnatilmoqda: {webhook_url}")
    try:
        await application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        logger.info("Webhook muvaffaqiyatli o'rnatildi.")
    except Exception as e:
        logger.error(f"Webhook o'rnatishda xatolik: {e}")

    yield

    # 3. Webhookni o'chirish va applicationni to'xtatish
    logger.info("Webhook o'chirilmoqda...")
    try:
        await application.bot.delete_webhook()
        logger.info("Webhook o'chirildi.")
    except Exception as e:
        logger.error(f"Webhook o'chirishda xatolik: {e}")
        
    await application.stop()
    await application.shutdown()


app = FastAPI(
    title="English Vocabulary Telegram Bot API",
    description="FastAPI + python-telegram-bot webhook integratsiyasi",
    version="1.0.0",
    lifespan=lifespan
)


@app.post(settings.WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """
    Telegram webhook so'rovlarini qabul qilish nuqtasi.
    """
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, application.bot)
        # Update-ni PTB navbatiga qo'shamiz, u fonda qayta ishlanadi
        await application.update_queue.put(update)
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Webhook update error: {e}", exc_info=True)
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.get("/")
async def home_route():
    """Bot statusini tekshirish uchun asosiy manzil."""
    return {
        "status": "online",
        "bot": "English Vocab Bot (python-telegram-bot)",
        "webhook_url": f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
    }


@app.get("/health")
async def health_check():
    """Server salomatligi tekshiruvi (Health Check)."""
    return {"status": "healthy"}
