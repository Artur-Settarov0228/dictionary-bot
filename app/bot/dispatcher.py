"""
Telegram bot Application obyekti va handlers bog'lamasi.
python-telegram-bot kutubxonasi uchun dispatcher vazifasini bajaradi.
"""
import logging
from telegram import BotCommand
from telegram.ext import Application

from app.core.config import settings
from app.core.database import create_tables

logger = logging.getLogger(__name__)


async def set_bot_commands(app: Application):
    """Bot menyusi buyruqlarini sozlash."""
    commands = [
        BotCommand("start", "Botni ishga tushirish"),
        BotCommand("admin", "Admin panelini ochish (Faqat adminlar uchun)"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Bot buyruqlari muvaffaqiyatli o'rnatildi.")


def setup_handlers(app: Application):
    """Barcha handlerlarni applicationga qo'shish."""
    from app.bot.handlers import admin_conversation, student_conversation, main_handlers

    # 1. Admin handlerlari
    app.add_handler(admin_conversation)

    # 2. O'quvchi test/start conversation handler
    app.add_handler(student_conversation)

    # 3. Qolgan umumiy handlerlar
    for handler in main_handlers:
        app.add_handler(handler)


async def post_init(app: Application):
    """
    PTB ishga tushganda (initialize) avtomatik ishlaydigan hook.
    Jadvallarni yaratadi, buyruqlarni sozlaydi va handlerlarni yuklaydi.
    """
    logger.info("Ma'lumotlar bazasi jadvallari tekshirilmoqda...")
    try:
        await create_tables()
        logger.info("Jadvallar muvaffaqiyatli tayyorlandi.")
    except Exception as e:
        logger.error(f"Jadvallarni yaratishda xato: {e}", exc_info=True)

    # Handlerlar va buyruqlarni yuklash
    setup_handlers(app)
    await set_bot_commands(app)
    
    # Webhookni vaqtincha tozalash (polling uchun)
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Webhook tozalashda xatolik: {e}")


# Application obyekti yaratiladi va post_init bog'lanadi
application = (
    Application.builder()
    .token(settings.BOT_TOKEN)
    .post_init(post_init)
    .connect_timeout(30.0)
    .read_timeout(30.0)
    .write_timeout(30.0)
    .pool_timeout(30.0)
    .get_updates_connect_timeout(30.0)
    .get_updates_read_timeout(40.0)
    .get_updates_write_timeout(30.0)
    .get_updates_pool_timeout(30.0)
    .build()
)
