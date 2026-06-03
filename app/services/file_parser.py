"""
.txt fayl parseri.
Fayl formati: english_word | [pronunciation] | uzbek_translation
Misol: actually | [ˈæktʃuəli] | asosan, haqiqatan
"""
import logging
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lesson, Word

logger = logging.getLogger(__name__)


def parse_txt_content(content: str) -> List[Tuple[str, str, str]]:
    """
    .txt fayl mazmunini tahlil qiladi va (so'z, talaffuz, tarjima) juftliklarini qaytaradi.

    Args:
        content: Fayl matni

    Returns:
        [(english_word, pronunciation, uzbek_translation), ...]
    """
    words: List[Tuple[str, str, str]] = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()

        # Bo'sh satrlar va sharhlarni o'tkazib yuborish
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("|")]

        if len(parts) < 2:
            logger.warning(f"Satr {line_num} noto'g'ri formatda, o'tkazib yuborildi: {line!r}")
            continue

        if len(parts) == 2:
            # Talaffuzsiz format: so'z | tarjima
            english_word, uzbek_translation = parts[0], parts[1]
            pronunciation = ""
        else:
            # To'liq format: so'z | talaffuz | tarjima
            english_word = parts[0]
            pronunciation = parts[1]
            uzbek_translation = parts[2]

        if not english_word or not uzbek_translation:
            logger.warning(f"Satr {line_num}: bo'sh so'z yoki tarjima, o'tkazildi.")
            continue

        words.append((english_word, pronunciation, uzbek_translation))

    return words


async def save_lesson_from_file(
    db: AsyncSession,
    filename: str,
    content: str,
) -> Tuple[Lesson, int]:
    """
    Fayl mazmunini tahlil qilib, bazaga Lesson va Word larni saqlaydi.

    Args:
        db: Asinxron DB sessiyasi
        filename: Fayl nomi (dars sarlavhasi sifatida ishlatiladi)
        content: Fayl matni (UTF-8)

    Returns:
        (yaratilgan Lesson obyekti, saqlangan so'zlar soni)
    """
    parsed_words = parse_txt_content(content)

    if not parsed_words:
        raise ValueError("Faylda birorta ham to'g'ri formatdagi so'z topilmadi.")

    # Dars sarlavhasini fayl nomidan olish (.txt kengaytmasini olib tashlaymiz)
    title = filename.replace(".txt", "").replace("_", " ").strip()

    # Yangi dars yaratish
    lesson = Lesson(title=title)
    db.add(lesson)
    await db.flush()  # ID olish uchun

    # So'zlarni darsga qo'shish
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

    logger.info(f"Dars saqlandi: '{title}' — {len(word_objects)} ta so'z.")
    return lesson, len(word_objects)
