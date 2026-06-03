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
    start_quiz_keyboard,
    view_vocab_keyboard,
    levels_keyboard,
    lessons_keyboard,
    lesson_menu_keyboard,
    back_to_lesson_menu_keyboard
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


async def select_level_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchiga darajalar (levels) ro'yxatini ko'rsatadi."""
    await update.message.reply_text(
        "📚 Iltimos, o'zingizning ingliz tili darajangizni tanlang:",
        reply_markup=levels_keyboard()
    )
    return ConversationHandler.END


async def select_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi darajani tanlaganda unga darslar ro'yxatini ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    level = data_parts[1]

    await query.edit_message_text(
        f"🌟 Daraja: <b>{level}</b>\n\n📖 Iltimos, darslardan birini tanlang:",
        reply_markup=lessons_keyboard(level),
        parse_mode="HTML"
    )


async def back_to_levels_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Orqaga, darajalar ro'yxatiga qaytish."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📚 Iltimos, o'zingizning ingliz tili darajangizni tanlang:",
        reply_markup=levels_keyboard()
    )


async def select_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi ma'lum bir darsni tanlaganda dars menyusini (Video/Lug'at/Test) chiqaradi."""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    level = data_parts[1]
    lesson_num = int(data_parts[2])

    async with AsyncSessionLocal() as db:
        # Barcha ushbu darajadagi darslarni olamiz
        stmt = select(Lesson).where(Lesson.level == level)
        res = await db.execute(stmt)
        lessons = res.scalars().all()

        # Dars nomidan raqamga mos keladiganini aniqlaymiz
        lesson = None
        for l in lessons:
            digits = "".join([c for c in l.title if c.isdigit()])
            if digits and int(digits) == lesson_num:
                lesson = l
                break

        # Agar dars bazada umuman yo'q bo'lsa, yaratib qo'yamiz (bo'sh dars)
        if not lesson:
            lesson = Lesson(title=f"Lesson {lesson_num}", level=level)
            db.add(lesson)
            await db.commit()
            await db.refresh(lesson)

        await query.answer()

        # Dars menyusi klaviaturasini chiqaramiz
        await query.edit_message_text(
            f"📖 <b>Daraja: {level} | {lesson_num}-dars</b>\n\n"
            f"Dars bilan tanishish uchun quyidagi bo'limlardan birini tanlang:",
            reply_markup=lesson_menu_keyboard(level, lesson_num, lesson.id),
            parse_mode="HTML"
        )


async def view_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Video darsni ko'rsatish callback so'rovi."""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    level = data_parts[1]
    lesson_num = int(data_parts[2])

    async with AsyncSessionLocal() as db:
        # Barcha ushbu darajadagi darslarni olamiz
        stmt = select(Lesson).where(Lesson.level == level)
        res = await db.execute(stmt)
        lessons = res.scalars().all()

        # Dars nomidan raqamga mos keladiganini aniqlaymiz
        lesson = None
        for l in lessons:
            digits = "".join([c for c in l.title if c.isdigit()])
            if digits and int(digits) == lesson_num:
                lesson = l
                break

        if not lesson or (not lesson.video_url and not lesson.topic):
            await query.answer("⚠️ Ushbu dars uchun video darslik yoki mavzu hali yuklanmagan!", show_alert=True)
            return

        await query.answer()

        # Agarda video_url telegram file_id bo'lsa (ya'ni http bilan boshlanmasa)
        if lesson.video_url and not lesson.video_url.startswith(("http://", "https://", "www.")):
            # Video faylini to'g'ridan-to'g'ri yuboramiz (avval video keyin document sifatida urinib ko'ramiz)
            try:
                await query.message.reply_video(
                    video=lesson.video_url,
                    caption=f"📹 <b>Daraja: {level} | {lesson_num}-dars video darsligi</b>" + (f"\n📚 Mavzu: <b>{lesson.topic}</b>" if lesson.topic else ""),
                    parse_mode="HTML"
                )
            except Exception:
                try:
                    await query.message.reply_document(
                        document=lesson.video_url,
                        caption=f"📹 <b>Daraja: {level} | {lesson_num}-dars video darsligi</b>" + (f"\n📚 Mavzu: <b>{lesson.topic}</b>" if lesson.topic else ""),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Video file_id yuborishda xato: {e}")
                    await query.message.reply_text("⚠️ Video faylni yuklashda xatolik yuz berdi.")

            # Dars menyusi tugmasini qayta yuboramiz
            await query.message.reply_text(
                "💡 Dars bilan tanishib bo'lgach, dars bo'limlariga qaytishingiz mumkin:",
                reply_markup=back_to_lesson_menu_keyboard(level, lesson_num)
            )
        else:
            # Video/mavzu ma'lumotlarini formatlash (http link yoki faqat mavzu bo'lsa)
            msg = f"📹 <b>Daraja: {level} | {lesson_num}-dars</b>\n\n"
            if lesson.topic:
                msg += f"📚 Dars mavzusi: <b>{lesson.topic}</b>\n\n"
            if lesson.video_url:
                msg += f"🔗 Video darslik: {lesson.video_url}\n\n"
            
            msg += f"💡 Dars bilan tanishib bo'lgach, quyidagi tugma orqali dars menyusiga qaytishingiz mumkin:"

            await query.edit_message_text(
                msg,
                reply_markup=back_to_lesson_menu_keyboard(level, lesson_num),
                parse_mode="HTML"
            )


async def view_audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """O'qilish audio talaffuzini yuborish callback so'rovi."""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    level = data_parts[1]
    lesson_num = int(data_parts[2])

    async with AsyncSessionLocal() as db:
        # Barcha ushbu darajadagi darslarni olamiz
        stmt = select(Lesson).where(Lesson.level == level)
        res = await db.execute(stmt)
        lessons = res.scalars().all()

        # Dars nomidan raqamga mos keladiganini aniqlaymiz
        lesson = None
        for l in lessons:
            digits = "".join([c for c in l.title if c.isdigit()])
            if digits and int(digits) == lesson_num:
                lesson = l
                break

        if not lesson or not lesson.audio_url:
            await query.answer("⚠️ Ushbu dars uchun talaffuz audiosi hali yuklanmagan!", show_alert=True)
            return

        await query.answer()

        # Audioni yuboramiz
        try:
            await query.message.reply_audio(
                audio=lesson.audio_url,
                caption=f"🔊 <b>Daraja: {level} | {lesson_num}-dars lug'at talaffuzi</b>",
                parse_mode="HTML"
            )
        except Exception:
            try:
                await query.message.reply_voice(
                    voice=lesson.audio_url,
                    caption=f"🔊 <b>Daraja: {level} | {lesson_num}-dars lug'at talaffuzi</b>",
                    parse_mode="HTML"
                )
            except Exception:
                try:
                    await query.message.reply_document(
                        document=lesson.audio_url,
                        caption=f"🔊 <b>Daraja: {level} | {lesson_num}-dars lug'at talaffuzi</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Audio yuborishda xato: {e}")
                    await query.message.reply_text("⚠️ Audio faylni yuborishda xatolik yuz berdi.")

        # Dars menyusi tugmasini qayta yuboramiz
        await query.message.reply_text(
            "💡 Dars bo'limlariga qaytishingiz mumkin:",
            reply_markup=back_to_lesson_menu_keyboard(level, lesson_num)
        )


async def view_vocab_words_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dars lug'atini ko'rsatish callback so'rovi."""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    level = data_parts[1]
    lesson_num = int(data_parts[2])

    async with AsyncSessionLocal() as db:
        # Barcha ushbu darajadagi darslarni olamiz
        stmt = select(Lesson).where(Lesson.level == level)
        res = await db.execute(stmt)
        lessons = res.scalars().all()

        # Dars nomidan raqamga mos keladiganini aniqlaymiz
        lesson = None
        for l in lessons:
            digits = "".join([c for c in l.title if c.isdigit()])
            if digits and int(digits) == lesson_num:
                lesson = l
                break

        if not lesson:
            await query.answer("⚠️ Dars ma'lumotlari topilmadi!", show_alert=True)
            return

        # Dars so'zlarini olamiz
        stmt_words = select(Word).where(Word.lesson_id == lesson.id).order_by(Word.id)
        res_words = await db.execute(stmt_words)
        words = res_words.scalars().all()

        if not words:
            await query.answer("⚠️ Ushbu dars uchun lug'at hali yuklanmagan!", show_alert=True)
            return

        await query.answer()

        # So'zlar ro'yxatini formatlash
        words_list = []
        for idx, w in enumerate(words, start=1):
            pron = f" {w.pronunciation}" if w.pronunciation else ""
            words_list.append(f"{idx}. <b>{w.english_word}</b>{pron} — {w.uzbek_translation}")

        words_text = "\n".join(words_list)

        # Lug'atni chiqarib dars menyusiga qaytish tugmasini qo'yamiz
        await query.edit_message_text(
            f"📖 <b>Daraja: {level} | {lesson_num}-dars lug'ati:</b>\n\n"
            f"{words_text}\n\n"
            f"💡 So'zlarni yaxshilab yodlab oling, so'ng dars menyusiga qaytib testni topshirishingiz mumkin:",
            reply_markup=back_to_lesson_menu_keyboard(level, lesson_num),
            parse_mode="HTML"
        )


async def back_to_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dars bo'limlaridan dars menyusiga qaytish."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    level = data_parts[1]
    lesson_num = int(data_parts[2])

    async with AsyncSessionLocal() as db:
        # Barcha ushbu darajadagi darslarni olamiz
        stmt = select(Lesson).where(Lesson.level == level)
        res = await db.execute(stmt)
        lessons = res.scalars().all()

        # Dars nomidan raqamga mos keladiganini aniqlaymiz
        lesson = None
        for l in lessons:
            digits = "".join([c for c in l.title if c.isdigit()])
            if digits and int(digits) == lesson_num:
                lesson = l
                break

        lesson_id = lesson.id if lesson else 0

        await query.edit_message_text(
            f"📖 <b>Daraja: {level} | {lesson_num}-dars</b>\n\n"
            f"Dars bilan tanishish uchun quyidagi bo'limlardan birini tanlang:",
            reply_markup=lesson_menu_keyboard(level, lesson_num, lesson_id),
            parse_mode="HTML"
        )


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
        MessageHandler(filters.Regex("^📚 Testni boshlash$"), select_level_menu),
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
from app.bot.handlers.admin import (
    process_broadcast_callback, students_count, students_results,
    admin_panel_start, admin_level_callback, admin_back_to_levels_callback,
    global_cancel
)

main_handlers = [
    CommandHandler("start", cmd_start),
    CommandHandler("admin", admin_panel_start),
    CommandHandler("cancel", global_cancel),
    MessageHandler(filters.Regex("^📊 O'quvchilar natijalari$"), students_results),
    MessageHandler(filters.Regex("^👥 O'quvchilar soni$"), students_count),
    MessageHandler(filters.Regex("^📈 Mening natijalarim$"), my_results),
    CallbackQueryHandler(process_broadcast_callback, pattern="^broadcast:"),
    CallbackQueryHandler(view_vocab_callback, pattern="^view_vocab:"),
    CallbackQueryHandler(select_level_callback, pattern="^select_level:"),
    CallbackQueryHandler(back_to_levels_callback, pattern="^back_to_levels$"),
    CallbackQueryHandler(select_lesson_callback, pattern="^select_lesson:"),
    CallbackQueryHandler(view_video_callback, pattern="^view_video:"),
    CallbackQueryHandler(view_audio_callback, pattern="^view_audio:"),
    CallbackQueryHandler(view_vocab_words_callback, pattern="^view_vocab_words:"),
    CallbackQueryHandler(back_to_lesson_callback, pattern="^back_to_lesson:"),
    CallbackQueryHandler(admin_level_callback, pattern="^admin_level:"),
    CallbackQueryHandler(admin_back_to_levels_callback, pattern="^admin_back_to_levels$"),
    MessageHandler(filters.Regex("^Bekor qilish$"), global_cancel)
]
