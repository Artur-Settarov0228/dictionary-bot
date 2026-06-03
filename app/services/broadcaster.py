"""
Broadcaster servisi — barcha o'quvchilarga xabar tarqatish.
python-telegram-bot kutubxonasi yordamida yozilgan.
"""
import asyncio
import logging
from typing import List

from telegram import Bot, InlineKeyboardMarkup
from telegram.error import Forbidden, RetryAfter, TelegramError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User

logger = logging.getLogger(__name__)

# Telegram flood limit: 30 msg/sek oshmasin
BROADCAST_DELAY = 0.05  # 50ms har bir xabar orasida


async def get_all_student_ids(db: AsyncSession) -> List[int]:
    """
    Bazadan barcha o'quvchilarning (admin bo'lmaganlar) telegram_id larini oladi.
    """
    result = await db.execute(
        select(User.telegram_id).where(User.is_admin.is_(False))
    )
    return list(result.scalars().all())


async def broadcast_message(
    bot: Bot,
    user_ids: List[int],
    text: str,
    parse_mode: str = "HTML",
    reply_markup: InlineKeyboardMarkup = None,
) -> dict:
    """
    Ko'rsatilgan foydalanuvchilarga xabar yuboradi.
    """
    sent = 0
    failed = 0
    blocked = 0

    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            sent += 1
            await asyncio.sleep(BROADCAST_DELAY)

        except Forbidden:
            # Foydalanuvchi botni bloklagan
            logger.warning(f"Foydalanuvchi botni bloklagan: {user_id}")
            blocked += 1

        except RetryAfter as e:
            # Flood limit — kutib, qayta urinish
            logger.warning(f"Flood limit, {e.retry_after}s kutilmoqda...")
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
                sent += 1
            except Exception as retry_err:
                logger.error(f"Qayta urinishda xato ({user_id}): {retry_err}")
                failed += 1

        except TelegramError as e:
            logger.error(f"Telegram xatosi ({user_id}): {e}")
            failed += 1

        except Exception as e:
            logger.error(f"Xabar yuborishda kutilmagan xato ({user_id}): {e}")
            failed += 1

    logger.info(
        f"Broadcast yakunlandi: yuborildi={sent}, "
        f"bloklangan={blocked}, xato={failed}"
    )
    return {"sent": sent, "failed": failed, "blocked": blocked}
