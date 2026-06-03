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
from app.bot.states import UPLOADING_FILE, ADDING_VIDEO, ADDING_AUDIO
from app.bot.keyboards import (
    admin_main_keyboard,
    broadcast_confirm_keyboard,
    start_quiz_keyboard,
    view_vocab_keyboard,
    admin_levels_keyboard,
    admin_lessons_keyboard,
    cancel_keyboard
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
    """Admin uchun dars yuklash darajalar ro'yxatini ko'rsatadi."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            await update.message.reply_text("Siz admin emassiz! ❌")
            return ConversationHandler.END

        # Harakat turini belgilaymiz
        context.user_data["admin_action"] = "upload_file"

        await update.message.reply_text(
            "📤 Iltimos, yangi darsni qaysi darajaga yuklamoqchisiz?",
            reply_markup=admin_levels_keyboard()
        )
        return ConversationHandler.END


async def add_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin uchun video dars qo'shish darajalar ro'yxatini ko'rsatadi."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            await update.message.reply_text("Siz admin emassiz! ❌")
            return ConversationHandler.END

        # Harakat turini belgilaymiz
        context.user_data["admin_action"] = "upload_video"

        await update.message.reply_text(
            "📹 Iltimos, video yuklanadigan dars darajasini tanlang:",
            reply_markup=admin_levels_keyboard()
        )
        return ConversationHandler.END


async def add_audio_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin uchun audio dars qo'shish darajalar ro'yxatini ko'rsatadi."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            await update.message.reply_text("Siz admin emassiz! ❌")
            return ConversationHandler.END

        # Harakat turini belgilaymiz
        context.user_data["admin_action"] = "upload_audio"

        await update.message.reply_text(
            "🔊 Iltimos, audio yuklanadigan dars darajasini tanlang (Faqat A1 va A2 uchun amal qiladi):",
            reply_markup=admin_levels_keyboard()
        )
        return ConversationHandler.END


async def admin_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin darajani tanlaganda unga yuklash uchun darslar ro'yxatini ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    level = data_parts[1]

    await query.edit_message_text(
        f"📤 Daraja: <b>{level}</b>\n\n📖 Yuklamoqchi bo'lgan darsingizni tanlang:",
        reply_markup=admin_lessons_keyboard(level),
        parse_mode="HTML"
    )


async def admin_back_to_levels_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Orqaga, yuklash uchun darajalar ro'yxatiga qaytish."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📤 Iltimos, yangi darsni qaysi darajaga yuklamoqchisiz?",
        reply_markup=admin_levels_keyboard()
    )


async def admin_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin ma'lum darsni tanlaganda undan dars turiga qarab fayl yoki link so'raydi."""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    level = data_parts[1]
    lesson_num = int(data_parts[2])

    # Daraja va dars raqamini context-da saqlaymiz
    context.user_data["upload_level"] = level
    context.user_data["upload_lesson_num"] = lesson_num

    action = context.user_data.get("admin_action", "upload_file")

    if action == "view_results":
        await show_results_for_lesson(update, context, level, lesson_num)
        return ConversationHandler.END

    if action == "upload_file":
        await query.delete_message()
        await query.message.reply_text(
            f"📥 <b>Daraja: {level} | {lesson_num}-dars</b> uchun <b>.txt</b> faylini yuboring.\n\n"
            f"Fayl formati quyidagicha bo'lishi kerak:\n"
            f"<code>english_word | [pronunciation] | uzbek_translation</code>\n\n"
            f"<i>Bekor qilish uchun /cancel deb yozing yoki quyidagi 'Bekor qilish' tugmasini bosing.</i>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return UPLOADING_FILE
    elif action == "upload_audio":
        await query.delete_message()
        await query.message.reply_text(
            f"🔊 <b>Daraja: {level} | {lesson_num}-dars</b> uchun talaffuz audio faylini (yoki ovozli xabarini) yuboring.\n\n"
            f"<i>Bekor qilish uchun /cancel deb yozing yoki quyidagi 'Bekor qilish' tugmasini bosing.</i>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return ADDING_AUDIO
    else:
        await query.delete_message()
        await query.message.reply_text(
            f"📹 <b>Daraja: {level} | {lesson_num}-dars</b> uchun video dars mavzusi va havolasini/faylini yuboring.\n\n"
            f"Siz quyidagilardan birini yuborishingiz mumkin:\n"
            f"1. <b>Video fayl</b> (to'g'ridan-to'g'ri yuborish, izoh/caption qismida dars mavzusini yozishingiz mumkin)\n"
            f"2. **Mavzu va havola birga**: <code>Mavzu nomi | https://link...</code>\n"
            f"3. **Faqat mavzu nomi**: <code>Mavzu nomi</code>\n"
            f"4. **Faqat havola**: <code>https://link...</code>\n\n"
            f"<i>Bekor qilish uchun /cancel deb yozing yoki quyidagi 'Bekor qilish' tugmasini bosing.</i>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return ADDING_VIDEO


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

            # So'zlarni tahlil qilish
            from app.services.file_parser import parse_txt_content
            parsed_words = parse_txt_content(content)
            if not parsed_words:
                raise ValueError("Faylda birorta ham to'g'ri formatdagi so'z topilmadi.")

            level = context.user_data.get("upload_level", "A1")
            lesson_num = context.user_data.get("upload_lesson_num", 1)
            lesson_title = f"Lesson {lesson_num}"

            # Mavjud darsni tekshiramiz (agar mavjud bo'lsa so'zlarini yangilaymiz)
            stmt_lesson = select(Lesson).where(Lesson.level == level, Lesson.title == lesson_title)
            res_lesson = await db.execute(stmt_lesson)
            lesson = res_lesson.scalar_one_or_none()

            from sqlalchemy import delete
            if lesson:
                # Eski so'zlarni o'chirib tashlaymiz
                await db.execute(delete(Word).where(Word.lesson_id == lesson.id))
            else:
                # Yangi dars yaratamiz
                lesson = Lesson(title=lesson_title, level=level)
                db.add(lesson)
                await db.flush()

            # Yangi so'zlarni saqlash
            word_objects = [
                Word(
                    lesson_id=lesson.id,
                    english_word=english,
                    pronunciation=pronunciation,
                    uzbek_translation=uzbek,
                )
                for english, pronunciation, uzbek in parsed_words
            ]
            db.add_all(word_objects)
            await db.commit()
            await db.refresh(lesson)
            words_count = len(word_objects)
            
            await status_msg.delete()
            await update.message.reply_text(
                f"✅ Yangi dars muvaffaqiyatli yuklandi!\n\n"
                f"🌟 Daraja: <b>{level}</b>\n"
                f"📌 Dars: <b>{lesson.title}</b>\n"
                f"📚 So'zlar soni: {words_count} ta",
                reply_markup=admin_main_keyboard(),
                parse_mode="HTML"
            )
            await update.message.reply_text(
                "📢 Ushbu dars haqida barcha o'quvchilarga xabar tarqatishni xohlaysizmi?",
                reply_markup=broadcast_confirm_keyboard(lesson.id)
            )
        except Exception as e:
            logger.error(f"Fayl saqlashda xato: {e}", exc_info=True)
            await status_msg.edit_text(f"Xatolik yuz berdi: {str(e)} ❌")
        
        # User ma'lumotlarini tozalash
        context.user_data.pop("upload_level", None)
        context.user_data.pop("upload_lesson_num", None)
        context.user_data.pop("admin_action", None)
        return ConversationHandler.END


async def process_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin yuborgan video havola/fayl va/yoki mavzuni saqlash."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return ConversationHandler.END

        level = context.user_data.get("upload_level", "A1")
        lesson_num = context.user_data.get("upload_lesson_num", 1)
        lesson_title = f"Lesson {lesson_num}"

        topic = None
        video_url = None

        if update.message.video:
            video_url = update.message.video.file_id
            topic = update.message.caption.strip() if update.message.caption else None
        elif update.message.document:
            video_url = update.message.document.file_id
            topic = update.message.caption.strip() if update.message.caption else None
        elif update.message.text:
            raw_text = update.message.text.strip()
            if "|" in raw_text:
                parts = [p.strip() for p in raw_text.split("|", 1)]
                topic = parts[0]
                video_url = parts[1]
            else:
                if raw_text.startswith(("http://", "https://", "www.")):
                    video_url = raw_text
                else:
                    topic = raw_text
        else:
            await update.message.reply_text("⚠️ Noto'g'ri format! Iltimos, video fayl, matn yoki havola yuboring.")
            return ADDING_VIDEO

        # Dars borligini tekshiramiz
        stmt_lesson = select(Lesson).where(Lesson.level == level, Lesson.title == lesson_title)
        res_lesson = await db.execute(stmt_lesson)
        lesson = res_lesson.scalar_one_or_none()

        if lesson:
            # Video va mavzuni yangilaymiz
            if topic is not None:
                lesson.topic = topic
            if video_url is not None:
                lesson.video_url = video_url
        else:
            # Yangi dars yaratamiz
            lesson = Lesson(title=lesson_title, level=level, topic=topic, video_url=video_url)
            db.add(lesson)

        await db.commit()
        await db.refresh(lesson)

        success_msg = (
            f"✅ Video dars/mavzu muvaffaqiyatli saqlandi!\n\n"
            f"🌟 Daraja: <b>{level}</b>\n"
            f"📌 Dars: <b>{lesson_title}</b>\n"
        )
        if lesson.topic:
            success_msg += f"📚 Mavzu: <b>{lesson.topic}</b>\n"
        if lesson.video_url:
            if lesson.video_url.startswith(("http://", "https://", "www.")):
                success_msg += f"🔗 Video havola: {lesson.video_url}\n"
            else:
                success_msg += f"📹 Video fayl saqlandi (Telegram File ID)\n"

        await update.message.reply_text(
            success_msg,
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML"
        )

        # User ma'lumotlarini tozalash
        context.user_data.pop("upload_level", None)
        context.user_data.pop("upload_lesson_num", None)
        context.user_data.pop("admin_action", None)
        return ConversationHandler.END


async def process_audio_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin yuborgan audio fayl yoki ovozli xabarni saqlash."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return ConversationHandler.END

        level = context.user_data.get("upload_level", "A1")
        lesson_num = context.user_data.get("upload_lesson_num", 1)
        lesson_title = f"Lesson {lesson_num}"

        audio_url = None

        if update.message.audio:
            audio_url = update.message.audio.file_id
        elif update.message.voice:
            audio_url = update.message.voice.file_id
        elif update.message.document:
            audio_url = update.message.document.file_id
        else:
            await update.message.reply_text("⚠️ Noto'g'ri format! Iltimos, audio fayl yoki ovozli xabar (voice) yuboring.")
            return ADDING_AUDIO

        # Dars borligini tekshiramiz
        stmt_lesson = select(Lesson).where(Lesson.level == level, Lesson.title == lesson_title)
        res_lesson = await db.execute(stmt_lesson)
        lesson = res_lesson.scalar_one_or_none()

        if lesson:
            lesson.audio_url = audio_url
        else:
            lesson = Lesson(title=lesson_title, level=level, audio_url=audio_url)
            db.add(lesson)

        await db.commit()

        await update.message.reply_text(
            f"✅ Talaffuz audiosi muvaffaqiyatli saqlandi!\n\n"
            f"🌟 Daraja: <b>{level}</b>\n"
            f"📌 Dars: <b>{lesson_title}</b>\n"
            f"🔊 Audio dars yuklandi.",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML"
        )

        # User ma'lumotlarini tozalash
        context.user_data.pop("upload_level", None)
        context.user_data.pop("upload_lesson_num", None)
        context.user_data.pop("admin_action", None)
        return ConversationHandler.END


async def global_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global bekor qilish xabari. Klaviaturalarni tiklaydi."""
    telegram_id = update.effective_user.id
    context.user_data.clear()
    
    async with AsyncSessionLocal() as db:
        if await is_admin_user(telegram_id, db):
            await update.message.reply_text("Bekor qilindi.", reply_markup=admin_main_keyboard())
        else:
            from app.bot.keyboards import student_main_keyboard
            await update.message.reply_text("Bekor qilindi.", reply_markup=student_main_keyboard())
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
            await query.message.reply_text("Admin paneli:", reply_markup=admin_main_keyboard())
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
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML"
        )


async def students_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika va o'quvchilar natijalarini ko'rish uchun darajalar menyusini ko'rsatadi."""
    async with AsyncSessionLocal() as db:
        if not await is_admin_user(update.effective_user.id, db):
            return

        # Harakat turini belgilaymiz
        context.user_data["admin_action"] = "view_results"

        await update.message.reply_text(
            "📊 O'quvchilar natijalarini ko'rish uchun dars darajasini tanlang:",
            reply_markup=admin_levels_keyboard()
        )


async def show_results_for_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE, level: str, lesson_num: int):
    """Tanlangan daraja va dars bo'yicha o'quvchilar natijalarini ko'rsatish."""
    query = update.callback_query
    await query.answer()

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
            await query.edit_message_text(
                f"📊 <b>Daraja: {level} | {lesson_num}-dars</b>\n\n"
                f"Ushbu dars bo'yicha hech qanday ma'lumot topilmadi! ❌",
                parse_mode="HTML"
            )
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
            await query.edit_message_text(
                f"📌 Daraja: <b>{level}</b> | Dars: <b>{lesson.title}</b>\n\n"
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
            f"📊 <b>Daraja: {level} | Dars: '{lesson.title}' bo'yicha statistika:</b>\n\n"
            f"👥 Qatnashganlar: <b>{total_participants} ta o'quvchi</b>\n"
            f"📈 O'rtacha o'zlashtirish: <b>{avg_score:.1f}%</b>\n\n"
            f"🏆 <b>Top 10 o'quvchilar:</b>\n" + "\n".join(top_list) + "\n\n"
        )

        if common_errors:
            msg_text += f"❌ <b>Eng ko'p xato qilingan so'zlar (Top 5):</b>\n" + "\n".join(common_errors)
        else:
            msg_text += f"❌ <b>Eng ko'p xato qilingan so'zlar:</b> Hali hech kim xato qilmadi!"

        await query.edit_message_text(msg_text, parse_mode="HTML")


# Admin ConversationHandler tuzilmasi
admin_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^📤 Dars yuklash$"), upload_lesson_start),
        MessageHandler(filters.Regex("^📹 Video dars qo'shish$"), add_video_start),
        MessageHandler(filters.Regex("^🔊 Audio dars qo'shish$"), add_audio_start),
        CallbackQueryHandler(admin_lesson_callback, pattern="^admin_lesson:")
    ],
    states={
        UPLOADING_FILE: [
            MessageHandler(filters.Document.ALL, process_lesson_file),
        ],
        ADDING_VIDEO: [
            MessageHandler((filters.TEXT | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND, process_video_link),
        ],
        ADDING_AUDIO: [
            MessageHandler((filters.AUDIO | filters.VOICE | filters.Document.ALL) & ~filters.COMMAND, process_audio_file),
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_upload),
        MessageHandler(filters.Regex("^Bekor qilish$"), cancel_upload),
    ]
)
