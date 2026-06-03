"""
Admin handlerlari python-telegram-bot uchun.
Dars yuklash (.txt), e'lon tarqatish va statistikalarni ko'rish.
"""
import io
import logging
from collections import Counter

from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.db.models import User, Lesson, Word, UserProgress
from app.bot.states import UPLOADING_FILE
from app.bot.keyboards import (
    admin_main_keyboard,
    broadcast_confirm_keyboard,
    start_quiz_keyboard,
    view_vocab_keyboard
)
from app.services.file_parser import save_lesson_from_file
from app.services.broadcaster import get_all_student_ids, broadcast_message

logger = logging.getLogger(__name__)


async def is_admin_user(telegram_id: int, db: AsyncSession) -> bool:
    """Foydalanuvchi admin ekanligini tekshiradi."""
    if telegram_id in settings.admin_ids_list:
        return True
    stmt = select(User.is_admin).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    is_admin = res.scalar_one_or_none()
    return bool(is_admin)


async def admin_panel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panelini ochish."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            await update.message.reply_text("Siz admin emassiz! ❌")
            return ConversationHandler.END

        await update.message.reply_text(
            "👋 Admin paneliga xush kelibsiz!",
            reply_markup=admin_main_keyboard()
        )
        return ConversationHandler.END


async def students_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha o'quvchilar sonini ko'rsatish."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return

        stmt = select(func.count(User.id)).where(User.is_admin.is_(False))
        res = await db.execute(stmt)
        count = res.scalar() or 0
        await update.message.reply_text(
            f"👥 Botdagi jami o'quvchilar soni: <b>{count} ta</b>",
            parse_mode="HTML"
        )


async def upload_lesson_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fayl yuklash jarayonini boshlash."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return ConversationHandler.END

        await update.message.reply_text(
            "📝 Iltimos, dars so'zlarini o'z ichiga olgan <b>.txt</b> faylini yuboring.\n\n"
            "Fayl formati quyidagicha bo'lishi kerak:\n"
            "<code>english_word | [pronunciation] | uzbek_translation</code>\n\n"
            "Misol:\n"
            "<code>actually | [ˈæktʃuəli] | asosan, haqiqatan\n"
            "beautiful | [ˈbjuːtɪfl] | chiroyli</code>",
            parse_mode="HTML"
        )
        return UPLOADING_FILE


async def process_lesson_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yuklangan faylni qabul qilish va saqlash."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return ConversationHandler.END

        document = update.message.document
        if not document.file_name.endswith(".txt"):
            await update.message.reply_text("Faqat .txt formatidagi fayllarni yuklashingiz mumkin! ❌")
            return UPLOADING_FILE

        status_msg = await update.message.reply_text("Fayl yuklanmoqda va tahlil qilinmoqda... ⏳")

        try:
            # Faylni yuklab olish
            file_obj = await context.bot.get_file(document.file_id)
            file_io = io.BytesIO()
            await file_obj.download_to_memory(out=file_io)
            content = file_io.getvalue().decode("utf-8")

            # Bazaga saqlash
            lesson, words_count = await save_lesson_from_file(db, document.file_name, content)
            
            await status_msg.delete()
            await update.message.reply_text(
                f"✅ Yangi dars muvaffaqiyatli saqlandi!\n\n"
                f"📌 Dars: <b>{lesson.title}</b>\n"
                f"📚 So'zlar soni: {words_count} ta",
                reply_markup=broadcast_confirm_keyboard(lesson.id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Fayl saqlashda xato: {e}", exc_info=True)
            await status_msg.edit_text(f"Xatolik yuz berdi: {str(e)} ❌")
        
        return ConversationHandler.END


async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fayl yuklashni bekor qilish."""
    await update.message.reply_text(
        "Fayl yuklash bekor qilindi.",
        reply_markup=admin_main_keyboard()
    )
    return ConversationHandler.END


async def process_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi darsni barcha o'quvchilarga tarqatish callback so'rovi."""
    query = update.callback_query
    await query.answer()
    
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(query.from_user.id, db):
            await query.edit_message_text("Ruxsat berilmagan! ❌")
            return

        data_parts = query.data.split(":")
        action = data_parts[1]

        if action == "cancel":
            await query.edit_message_text("📢 Xabar tarqatish bekor qilindi.")
            return

        lesson_id = int(action)
        
        # Darsni olish
        stmt = select(Lesson).where(Lesson.id == lesson_id)
        res = await db.execute(stmt)
        lesson = res.scalar_one_or_none()

        if not lesson:
            await query.edit_message_text("Dars topilmadi! ❌")
            return

        await query.edit_message_text("📢 Xabar tarqatish boshlandi... ⏳")

        student_ids = await get_all_student_ids(db)
        
        if not student_ids:
            await query.message.reply_text("Botda hali o'quvchilar yo'q. 👥")
            return

        # Broadcast yuborish
        text = (
            f"📚 <b>Yangi dars yuklandi: {lesson.title}!</b>\n\n"
            f"Ushbu dars bo'yicha lug'atni ko'rish va yodlashni boshlaymizmi? 🚀"
        )
        
        result = await broadcast_message(
            bot=context.bot,
            user_ids=student_ids,
            text=text,
            reply_markup=view_vocab_keyboard(lesson.id)
        )

        await query.message.reply_text(
            f"📢 <b>Xabar tarqatish yakunlandi:</b>\n"
            f"✅ Yuborildi: {result['sent']} ta\n"
            f"🚫 Bloklagan: {result['blocked']} ta\n"
            f"❌ Xatolik: {result['failed']} ta",
            parse_mode="HTML"
        )


async def students_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika va o'quvchilar natijalarini ko'rsatish."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return

        # Eng so'nggi darsni topish
        stmt_last_lesson = select(Lesson).order_by(desc(Lesson.created_at)).limit(1)
        res_last_lesson = await db.execute(stmt_last_lesson)
        lesson = res_last_lesson.scalar_one_or_none()

        if not lesson:
            await update.message.reply_text("Bazada hech qanday dars mavjud emas! ❌")
            return

        # Barcha o'quvchilar progressini olish
        stmt_progress = (
            select(UserProgress, User.fullname)
            .join(User, UserProgress.user_id == User.id)
            .where(UserProgress.lesson_id == lesson.id)
            .order_by(desc(UserProgress.score_percentage), UserProgress.completed_at)
        )
        res_progress = await db.execute(stmt_progress)
        progress_rows = res_progress.all()

        if not progress_rows:
            await update.message.reply_text(
                f"📌 Dars: <b>{lesson.title}</b>\n\n"
                f"Ushbu dars bo'yicha hali birorta ham o'quvchi test topshirmadi. 🤷‍♂️",
                parse_mode="HTML"
            )
            return

        # 1. Barcha urinishlarni xronologik tartibda olib, har bir urinish raqamini hisoblaymiz
        stmt_all_attempts = (
            select(UserProgress.id, UserProgress.user_id)
            .where(UserProgress.lesson_id == lesson.id)
            .order_by(UserProgress.completed_at)
        )
        res_attempts = await db.execute(stmt_all_attempts)
        all_attempts = res_attempts.all()

        attempt_map = {}
        user_attempts_count = {}
        for attempt_id, user_id in all_attempts:
            user_attempts_count[user_id] = user_attempts_count.get(user_id, 0) + 1
            attempt_map[attempt_id] = user_attempts_count[user_id]

        # 2. Har bir foydalanuvchining faqat eng yaxshi natijasini tanlab olamiz (unikal ro'yxat)
        unique_progress = []
        seen_users = set()
        for row in progress_rows:
            prog, fullname = row
            if prog.user_id not in seen_users:
                seen_users.add(prog.user_id)
                unique_progress.append(row)

        # Statistika hisoblash
        total_participants = len(unique_progress)
        avg_score = sum(row[0].score_percentage for row in unique_progress) / total_participants if total_participants > 0 else 0.0

        # Top 10 o'quvchi
        top_10 = unique_progress[:10]
        top_list = []
        for idx, (prog, fullname) in enumerate(top_10, start=1):
            attempt_num = attempt_map.get(prog.id, 1)
            top_list.append(f"{idx}. {fullname} ({attempt_num}-urinish) — <b>{prog.score_percentage}%</b>")

        # Eng ko'p xato qilingan so'zlar
        wrong_words_counter = Counter()
        for row in progress_rows:
            prog = row[0]
            if prog.wrong_words:
                for item in prog.wrong_words:
                    word_en = item.get("word")
                    if word_en:
                        wrong_words_counter[word_en] += 1

        common_errors = []
        for word_en, count in wrong_words_counter.most_common(5):
            common_errors.append(f"• <b>{word_en}</b> — {count} marta xato qilindi")

        msg_text = (
            f"📊 <b>Dars: '{lesson.title}' bo'yicha statistika:</b>\n\n"
            f"👥 Qatnashganlar: <b>{total_participants} ta o'quvchi</b>\n"
            f"📈 O'rtacha o'zlashtirish: <b>{avg_score:.1f}%</b>\n\n"
            f"🏆 <b>Top 10 o'quvchilar:</b>\n" + "\n".join(top_list) + "\n\n"
        )

        if common_errors:
            msg_text += f"❌ <b>Eng ko'p xato qilingan so'zlar (Top 5):</b>\n" + "\n".join(common_errors)
        else:
            msg_text += f"❌ <b>Eng ko'p xato qilingan so'zlar:</b> Hali hech kim xato qilmadi!"

        await update.message.reply_text(msg_text, parse_mode="HTML")


# Admin ConversationHandler tuzilmasi
admin_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^📤 Dars yuklash$"), upload_lesson_start),
    ],
    states={
        UPLOADING_FILE: [
            MessageHandler(filters.Document.ALL, process_lesson_file),
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_upload),
        MessageHandler(filters.Regex("^Bekor qilish$"), cancel_upload),
    ]
)
