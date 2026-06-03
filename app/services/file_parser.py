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
    """
    if content.strip().startswith(r"{\rtf"):
        raise ValueError("Fayl RTF formatida (TextEdit). Iltimos, faylni oddiy matn (Plain Text) ko'rinishida saqlang (Mac-da Format -> Make Plain Text).")

    words: List[Tuple[str, str, str]] = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()

        # Bo'sh satrlar va sharhlarni o'tkazib yuborish
        if not line or line.startswith("#"):
            continue

        import re

        # Avval | bilan ajratishga harakat qilamiz
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                english_word = parts[0]
                if len(parts) >= 3:
                    pronunciation = parts[1]
                    uzbek_translation = parts[2]
                else:
                    pronunciation = ""
                    uzbek_translation = parts[1]
            else:
                logger.warning(f"Satr {line_num} noto'g'ri formatda, o'tkazib yuborildi: {line!r}")
                continue
        else:
            # Demak | ishlatilmagan. Regex orqali tahlil qilamiz.
            # 1. format: [Raqam.] [Inglizcha so'z] [talaffuz] [chiziqcha/tenglik] [Tarjima]
            # Misol: 1. Shop assistant [shop ə-sis-tənt] – sotuvchi yordamchisi
            match = re.match(r'^(?:\d+\.\s*)?(.*?)\s*(?:\[(.*?)\])?\s*[-–—=:\t]+\s*(.*)$', line)
            
            if match:
                english_word = match.group(1).strip()
                pronunciation = match.group(2).strip() if match.group(2) else ""
                uzbek_translation = match.group(3).strip()
            else:
                logger.warning(f"Satr {line_num} noto'g'ri formatda, o'tkazib yuborildi: {line!r}")
                continue

        # Keraksiz belgilarni tozalash (masalan, agar rtf yoki boshqa xato bo'lsa)
        english_word = english_word.replace("\\", "").strip()
        uzbek_translation = uzbek_translation.replace("\\", "").strip()
        
        # Agar "1. " english_word ichida qolib ketgan bo'lsa (regex ushlamagan holatlarda), olib tashlash
        english_word = re.sub(r'^\d+\.\s*', '', english_word)

        if not english_word or not uzbek_translation:
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
        # Faylning boshlanishini ko'rsatamiz, shunda muammo nima ekanligini ko'rish oson bo'ladi
        head = content[:100].replace("\n", " ")
        raise ValueError(f"Faylda birorta ham to'g'ri formatdagi so'z topilmadi.\nFayl boshi: {head!r}")

    import re
    # Fayl nomidan daraja va dars nomini aniqlash (Masalan: A1_Lesson_1.txt -> level="A1", title="Lesson 1")
    name_without_ext = filename.replace(".txt", "").strip()
    
    # Bo'lish qoidalari: A1_Lesson_1 yoki A1 - Lesson 1
    parts = re.split(r'[_|-]', name_without_ext, maxsplit=1)
    
    level = "A1"
    title = name_without_ext
    
    if len(parts) == 2:
        parsed_level = parts[0].strip().upper()
        if parsed_level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            level = parsed_level
            title = parts[1].replace("_", " ").strip()

    # Yangi dars yaratish
    lesson = Lesson(title=title, level=level)
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
