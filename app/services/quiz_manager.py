"""
Quiz manager — test jarayonini boshqarish va natijalarni hisoblash.
"""
import random
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Word, UserProgress, User, Lesson

logger = logging.getLogger(__name__)

# FSM state'dagi ma'lumotlar kalitlari
QUIZ_WORDS_KEY = "quiz_words"          # [{"id": ..., "en": ..., "pron": ..., "uz": ...}]
QUIZ_INDEX_KEY = "quiz_current_index"  # hozirgi savol raqami
QUIZ_CORRECT_KEY = "quiz_correct"      # to'g'ri javoblar soni
QUIZ_WRONG_KEY = "quiz_wrong_words"    # xato qilingan so'zlar ro'yxati
QUIZ_LESSON_KEY = "quiz_lesson_id"     # test qilinayotgan dars ID si
QUIZ_OPTIONS_KEY = "quiz_options"      # hozirgi savol variantlari


async def get_lesson_words(db: AsyncSession, lesson_id: int) -> List[Dict[str, Any]]:
    """
    Darsning barcha so'zlarini bazadan oladi va aralashtirib qaytaradi.

    Args:
        db: DB sessiyasi
        lesson_id: Dars IDsi

    Returns:
        Aralashtirilgan so'zlar ro'yxati (dict formatida)
    """
    result = await db.execute(
        select(Word).where(Word.lesson_id == lesson_id)
    )
    words = result.scalars().all()

    if not words:
        return []

    word_list = [
        {
            "id": w.id,
            "en": w.english_word,
            "pron": w.pronunciation or "",
            "uz": w.uzbek_translation,
        }
        for w in words
    ]
    random.shuffle(word_list)
    return word_list


def generate_options(
    correct_word: Dict[str, Any],
    all_words: List[Dict[str, Any]],
    count: int = 4,
) -> List[str]:
    """
    To'g'ri javob + 3 ta xato variantni aralashtirib qaytaradi.

    Args:
        correct_word: To'g'ri so'z (dict)
        all_words: Barcha so'zlar ro'yxati
        count: Variantlar soni (default: 4)

    Returns:
        Aralashtirilgan [tarjima, ...] ro'yxati
    """
    correct_translation = correct_word["uz"]

    # Noto'g'ri variantlar uchun boshqa so'zlarning tarjimalarini olish
    other_translations = [
        w["uz"] for w in all_words
        if w["id"] != correct_word["id"] and w["uz"] != correct_translation
    ]

    # Agar yetarli variant bo'lmasa, mavjudlarini ishlatamiz
    wrong_count = min(count - 1, len(other_translations))
    wrong_options = random.sample(other_translations, wrong_count)

    options = wrong_options + [correct_translation]
    random.shuffle(options)
    return options


def build_question_text(word: Dict[str, Any], index: int, total: int) -> str:
    """
    Savol matni yaratadi.

    Args:
        word: So'z dict
        index: Hozirgi savol raqami (0-indexed)
        total: Jami savollar soni

    Returns:
        Formatlangan savol matni
    """
    pron_line = f"\n🗣 {word['pron']}" if word["pron"] else ""
    return (
        f"📝 Savol {index + 1}/{total}\n\n"
        f"🇬🇧 <b>{word['en']}</b>{pron_line}\n\n"
        f"✍️ Quyidagilardan to'g'ri tarjimani tanlang:"
    )


async def save_quiz_result(
    db: AsyncSession,
    telegram_id: int,
    lesson_id: int,
    correct_count: int,
    total_count: int,
    wrong_words: List[Dict[str, Any]],
) -> UserProgress:
    """
    Test natijasini bazaga saqlaydi.

    Args:
        db: DB sessiyasi
        telegram_id: Foydalanuvchi Telegram IDsi
        lesson_id: Dars IDsi
        correct_count: To'g'ri javoblar soni
        total_count: Jami savollar soni
        wrong_words: Xato qilingan so'zlar ro'yxati

    Returns:
        Saqlangan UserProgress obyekti
    """
    # Foydalanuvchini topish
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError(f"Foydalanuvchi topilmadi: telegram_id={telegram_id}")

    score = round((correct_count / total_count) * 100, 1) if total_count > 0 else 0.0

    progress = UserProgress(
        user_id=user.id,
        lesson_id=lesson_id,
        score_percentage=score,
        wrong_words=wrong_words,
    )
    db.add(progress)
    await db.commit()
    await db.refresh(progress)

    logger.info(
        f"Natija saqlandi: user_id={user.id}, lesson_id={lesson_id}, "
        f"score={score}%, wrong={len(wrong_words)}"
    )
    return progress


def format_final_result(
    correct_count: int,
    total_count: int,
    wrong_words: List[Dict[str, Any]],
) -> str:
    """
    Yakuniy natija xabarini formatlaydi.

    Args:
        correct_count: To'g'ri javoblar soni
        total_count: Jami savollar soni
        wrong_words: Xato qilingan so'zlar ro'yxati

    Returns:
        Formatlangan natija matni
    """
    score = round((correct_count / total_count) * 100, 1) if total_count > 0 else 0.0

    if score >= 90:
        emoji = "🏆"
        comment = "Ajoyib natija! Siz zo'rsiz!"
    elif score >= 70:
        emoji = "🎉"
        comment = "Yaxshi natija! Davom eting!"
    elif score >= 50:
        emoji = "💪"
        comment = "Qoniqarli. Ko'proq mashq qiling!"
    else:
        emoji = "📚"
        comment = "Yana o'rganib chiqing, siz uddalaysiz!"

    lines = [
        f"{emoji} <b>Test yakunlandi!</b>",
        "",
        f"✅ To'g'ri: {correct_count}/{total_count}",
        f"📊 Ball: <b>{score}%</b>",
        f"💬 {comment}",
    ]

    if wrong_words:
        lines += ["", "❌ <b>Xato qilingan so'zlar:</b>"]
        for item in wrong_words[:10]:  # Ko'pi bilan 10 ta ko'rsatamiz
            lines.append(
                f"  • <b>{item['word']}</b> → {item['correct']}"
                f" (siz: {item['given']})"
            )
        if len(wrong_words) > 10:
            lines.append(f"  ... va yana {len(wrong_words) - 10} ta")

    return "\n".join(lines)
