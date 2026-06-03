"""
O'quvchi handlerlari python-telegram-bot uchun.
Foydalanuvchi ro'yxatdan o'tishi (/start), test topshirishi (ConversationHandler)
va natijalarini ko'rishi.
"""
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.db.models import User, Lesson, Word, UserProgress
from app.bot.states import SELECTING_LESSON, ANSWERING_QUESTION
from app.bot.keyboards import (
    student_main_keyboard,
    quiz_options_keyboard,
    remove_keyboard,
    start_quiz_keyboard
)
from app.services.quiz_manager import (
    get_lesson_words,
    generate_options,
    build_question_text,
    save_quiz_result,
    format_final_result,
    QUIZ_WORDS_KEY,
    QUIZ_INDEX_KEY,
    QUIZ_CORRECT_KEY,
    QUIZ_WRONG_KEY,
    QUIZ_LESSON_KEY,
    QUIZ_OPTIONS_KEY
)

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buyrug'i."""
    telegram_id = update.effective_user.id
    fullname = update.effective_user.full_name or "Foydalanuvchi"

    # Context user_data ni tozalash
    context.user_data.clear()

    async with AsyncSessionLocal() as db:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=telegram_id,
                fullname=fullname,
                is_admin=False
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Yangi o'quvchi ro'yxatdan o'tdi: {fullname} (ID: {telegram_id})")

    await update.message.reply_text(
        f"👋 Assalomu alaykum, <b>{fullname}</b>!\n\n"
        f"Ingliz tili so'z boyligingizni tekshirish botiga xush kelibsiz. "
        f"Darslarni boshlash uchun quyidagi tugmalardan foydalaning.",
        reply_markup=student_main_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def select_lesson_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oxirgi dars so'zlarini ko'rsatadi va testni boshlash imkoniyatini beradi."""
    async with AsyncSessionLocal() as db:
        stmt = select(Lesson).order_by(desc(Lesson.created_at)).limit(1)
        res = await db.execute(stmt)
        lesson = res.scalar_one_or_none()

        if not lesson:
            await update.message.reply_text(
                "Hozircha hech qanday dars yuklanmagan. Iltimos, keyinroq urinib ko'ring! 📚"
            )
            return ConversationHandler.END

        # Dars so'zlarini olish
        stmt_words = select(Word).where(Word.lesson_id == lesson.id).order_by(Word.id)
        res_words = await db.execute(stmt_words)
        words = res_words.scalars().all()

        if not words:
            await update.message.reply_text("Ushbu darsda so'zlar topilmadi. ❌")
            return ConversationHandler.END

        # So'zlar ro'yxatini formatlash
        words_list = []
        for idx, w in enumerate(words, start=1):
            pron = f" {w.pronunciation}" if w.pronunciation else ""
            words_list.append(f"{idx}. <b>{w.english_word}</b>{pron} — {w.uzbek_translation}")

        words_text = "\n".join(words_list)

        await update.message.reply_text(
            f"📖 <b>Dars: '{lesson.title}' so'zligi:</b>\n\n"
            f"{words_text}\n\n"
            f"💡 So'zlarni yaxshilab yodlab oling. Tayyor bo'lganingizdan keyin testni boshlash uchun quyidagi tugmani bosing:",
            reply_markup=start_quiz_keyboard(lesson.id),
            parse_mode="HTML"
        )
        return SELECTING_LESSON


async def process_start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline tugma orqali testni boshlash."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    action = data_parts[1]

    if action == "later":
        await query.edit_message_text("⏰ Mayli, keyinroq boshlashingiz mumkin. Omad!")
        return ConversationHandler.END

    lesson_id = int(action)
    
    async with AsyncSessionLocal() as db:
        words = await get_lesson_words(db, lesson_id)
        if not words:
            await query.edit_message_text("Ushbu darsda so'zlar topilmadi yoki dars o'chirib yuborilgan. ❌")
            return ConversationHandler.END

        # FSM ma'lumotlarini context.user_data ga saqlaymiz
        context.user_data.clear()
        
        current_index = 0
        correct_word = words[current_index]
        options = generate_options(correct_word, words)

        context.user_data[QUIZ_WORDS_KEY] = words
        context.user_data[QUIZ_INDEX_KEY] = current_index
        context.user_data[QUIZ_CORRECT_KEY] = 0
        context.user_data[QUIZ_WRONG_KEY] = []
        context.user_data[QUIZ_LESSON_KEY] = lesson_id
        context.user_data[QUIZ_OPTIONS_KEY] = options

        # Inline tugmani o'chirib, birinchi savolni yuboramiz
        await query.delete_message()
        
        question_text = build_question_text(correct_word, current_index, len(words))
        await query.message.reply_text(
            question_text,
            reply_markup=quiz_options_keyboard(options),
            parse_mode="HTML"
        )
        return ANSWERING_QUESTION


async def view_vocab_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """E'londan keyin dars so'zligini ko'rish callback so'rovi."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    lesson_id = int(data_parts[1])

    async with AsyncSessionLocal() as db:
        # Darsni olish
        stmt = select(Lesson).where(Lesson.id == lesson_id)
        res = await db.execute(stmt)
        lesson = res.scalar_one_or_none()

        if not lesson:
            await query.edit_message_text("Dars topilmadi! ❌")
            return

        # Dars so'zlarini olish
        stmt_words = select(Word).where(Word.lesson_id == lesson_id).order_by(Word.id)
        res_words = await db.execute(stmt_words)
        words = res_words.scalars().all()

        if not words:
            await query.edit_message_text("Ushbu darsda so'zlar topilmadi. ❌")
            return

        # So'zlar ro'yxatini formatlash
        words_list = []
        for idx, w in enumerate(words, start=1):
            pron = f" {w.pronunciation}" if w.pronunciation else ""
            words_list.append(f"{idx}. <b>{w.english_word}</b>{pron} — {w.uzbek_translation}")

        words_text = "\n".join(words_list)

        # Xabarni tahrirlaymiz
        await query.edit_message_text(
            f"📖 <b>Dars: '{lesson.title}' so'zligi:</b>\n\n"
            f"{words_text}\n\n"
            f"💡 So'zlarni yaxshilab yodlab oling. Tayyor bo'lganingizdan keyin testni boshlash uchun quyidagi tugmani bosing:",
            reply_markup=start_quiz_keyboard(lesson.id),
            parse_mode="HTML"
        )


async def process_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test savoliga javob berishni qayta ishlash."""
    user_data = context.user_data
    
    words = user_data.get(QUIZ_WORDS_KEY, [])
    current_index = user_data.get(QUIZ_INDEX_KEY, 0)
    correct_count = user_data.get(QUIZ_CORRECT_KEY, 0)
    wrong_words = user_data.get(QUIZ_WRONG_KEY, [])
    lesson_id = user_data.get(QUIZ_LESSON_KEY)
    options = user_data.get(QUIZ_OPTIONS_KEY, [])

    if not words or current_index >= len(words):
        await update.message.reply_text(
            "Xatolik yuz berdi. Iltimos, testni qaytadan boshlang.",
            reply_markup=student_main_keyboard()
        )
        user_data.clear()
        return ConversationHandler.END

    user_answer = update.message.text.strip()
    correct_word = words[current_index]
    correct_translation = correct_word["uz"]

    # Foydalanuvchi variantlardan birini tanlaganini tekshirish
    if user_answer not in options:
        await update.message.reply_text(
            "⚠️ Iltimos, quyidagi variantlardan birini tanlang!",
            reply_markup=quiz_options_keyboard(options)
        )
        return ANSWERING_QUESTION

    # To'g'ri/xatoligini tekshirish
    feedback = ""
    if user_answer == correct_translation:
        correct_count += 1
        feedback = "✅ <b>To'g'ri!</b>"
    else:
        wrong_words.append({
            "word": correct_word["en"],
            "correct": correct_translation,
            "given": user_answer
        })
        feedback = f"❌ <b>Noto'g'ri!</b>\nTo'g'ri javob: <b>{correct_translation}</b>"

    # Feedbackni alohida xabar sifatida yuborish
    await update.message.reply_text(feedback, parse_mode="HTML")

    next_index = current_index + 1

    # Test tugaganini tekshirish
    if next_index >= len(words):
        # Natijani saqlash
        async with AsyncSessionLocal() as db:
            try:
                await save_quiz_result(
                    db=db,
                    telegram_id=update.effective_user.id,
                    lesson_id=lesson_id,
                    correct_count=correct_count,
                    total_count=len(words),
                    wrong_words=wrong_words
                )
                
                result_text = format_final_result(correct_count, len(words), wrong_words)
                await update.message.reply_text(
                    result_text,
                    reply_markup=student_main_keyboard(),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Test natijasini saqlashda xato: {e}", exc_info=True)
                await update.message.reply_text(
                    "Natijangiz hisoblandi, biroq bazaga saqlashda xatolik yuz berdi. ❌",
                    reply_markup=student_main_keyboard()
                )
        
        user_data.clear()
        return ConversationHandler.END
    else:
        # Keyingi savolga o'tish
        next_word = words[next_index]
        next_options = generate_options(next_word, words)

        user_data[QUIZ_INDEX_KEY] = next_index
        user_data[QUIZ_CORRECT_KEY] = correct_count
        user_data[QUIZ_WRONG_KEY] = wrong_words
        user_data[QUIZ_OPTIONS_KEY] = next_options

        question_text = build_question_text(next_word, next_index, len(words))
        await update.message.reply_text(
            question_text,
            reply_markup=quiz_options_keyboard(next_options),
            parse_mode="HTML"
        )
        return ANSWERING_QUESTION


async def my_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchining shaxsiy test natijalari tarixini ko'rsatish."""
    telegram_id = update.effective_user.id

    async with AsyncSessionLocal() as db:
        # Foydalanuvchini topish
        stmt_user = select(User).where(User.telegram_id == telegram_id)
        res_user = await db.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            await update.message.reply_text("Foydalanuvchi topilmadi. Qaytadan /start bosing. ❌")
            return

        # Foydalanuvchining barcha progresslarini olish
        stmt_progress = (
            select(UserProgress, Lesson.title)
            .join(Lesson, UserProgress.lesson_id == Lesson.id)
            .where(UserProgress.user_id == user.id)
            .order_by(desc(UserProgress.completed_at))
            .limit(10)
        )
        res_progress = await db.execute(stmt_progress)
        progress_rows = res_progress.all()

        if not progress_rows:
            await update.message.reply_text("Siz hali birorta ham test topshirmagansiz! 📚")
            return

        lines = ["📈 <b>Mening so'nggi natijalarim (Top 10):</b>\n"]
        for prog, lesson_title in progress_rows:
            date_str = prog.completed_at.strftime("%d.%m.%Y %H:%M")
            lines.append(
                f"📍 {lesson_title} — <b>{prog.score_percentage}%</b>\n"
                f"   🕒 <i>{date_str}</i>"
            )

        await update.message.reply_text("\n\n".join(lines), parse_mode="HTML")


async def cancel_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Testni bekor qilish."""
    context.user_data.clear()
    await update.message.reply_text(
        "Test bekor qilindi.",
        reply_markup=student_main_keyboard()
    )
    return ConversationHandler.END


# O'quvchi ConversationHandler
student_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^📚 Testni boshlash$"), select_lesson_and_start),
        CallbackQueryHandler(process_start_quiz_callback, pattern="^start_quiz:")
    ],
    states={
        SELECTING_LESSON: [
            CallbackQueryHandler(process_start_quiz_callback, pattern="^start_quiz:")
        ],
        ANSWERING_QUESTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_quiz_answer)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_quiz),
        MessageHandler(filters.Regex("^Bekor qilish$"), cancel_quiz),
    ]
)

# Boshqa umumiy handlerlar
from app.bot.handlers.admin import process_broadcast_callback, students_count, students_results, admin_panel_start

main_handlers = [
    CommandHandler("start", cmd_start),
    CommandHandler("admin", admin_panel_start),
    MessageHandler(filters.Regex("^📊 O'quvchilar natijalari$"), students_results),
    MessageHandler(filters.Regex("^👥 O'quvchilar soni$"), students_count),
    MessageHandler(filters.Regex("^📈 Mening natijalarim$"), my_results),
    CallbackQueryHandler(process_broadcast_callback, pattern="^broadcast:"),
    CallbackQueryHandler(view_vocab_callback, pattern="^view_vocab:")
]
