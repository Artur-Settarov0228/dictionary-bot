"""
Tugmalar (Reply va Inline klaviaturalar) python-telegram-bot uchun.
"""
from telegram import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)


# ─── Admin Reply tugmalari ────────────────────────────────────────────────────

def admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Admin asosiy tugmalar paneli."""
    keyboard = [
        [KeyboardButton(text="📤 Dars yuklash")],
        [KeyboardButton(text="📹 Video dars qo'shish")],
        [KeyboardButton(text="🔊 Audio dars qo'shish")],
        [KeyboardButton(text="📊 O'quvchilar natijalari")],
        [KeyboardButton(text="👥 O'quvchilar soni")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# ─── Admin Inline tugmalari ───────────────────────────────────────────────────

def broadcast_confirm_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Dars yuklangach, barcha o'quvchilarga yuborish tasdiqlash tugmasi."""
    keyboard = [
        [InlineKeyboardButton(
            text="📢 Barcha o'quvchilarga yuborish",
            callback_data=f"broadcast:{lesson_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="broadcast:cancel"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


# ─── O'quvchi Reply tugmalari ─────────────────────────────────────────────────

def student_main_keyboard() -> ReplyKeyboardMarkup:
    """O'quvchi asosiy tugmalar paneli."""
    keyboard = [
        [KeyboardButton(text="📚 Testni boshlash")],
        [KeyboardButton(text="📈 Mening natijalarim")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def quiz_options_keyboard(options: list[str]) -> ReplyKeyboardMarkup:
    """
    Test variantlari klaviaturasi.

    Args:
        options: 4 ta variant matni

    Returns:
        ReplyKeyboardMarkup — har satrda 2 ta variant
    """
    keyboard = []
    for i in range(0, len(options), 2):
        row = [KeyboardButton(text=opt) for opt in options[i:i+2]]
        keyboard.append(row)
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def start_quiz_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """'Testni boshlash' inline tugmasi (broadcast xabari uchun)."""
    keyboard = [
        [InlineKeyboardButton(
            text="✅ Ha, testni boshlayman!",
            callback_data=f"start_quiz:{lesson_id}"
        )],
        [InlineKeyboardButton(
            text="⏰ Keyinroq",
            callback_data="start_quiz:later"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def view_vocab_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Yangi dars yuklanganda, lug'atni ko'rish tugmasi."""
    keyboard = [
        [InlineKeyboardButton(
            text="📖 Lug'atni yodlash",
            callback_data=f"view_vocab:{lesson_id}"
        )],
        [InlineKeyboardButton(
            text="⏰ Keyinroq",
            callback_data="start_quiz:later"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def levels_keyboard() -> InlineKeyboardMarkup:
    """Darajalar (levels) inline klaviaturasi."""
    keyboard = [
        [
            InlineKeyboardButton(text="🇦1 (A1)", callback_data="select_level:A1"),
            InlineKeyboardButton(text="🇦2 (A2)", callback_data="select_level:A2")
        ],
        [
            InlineKeyboardButton(text="🇧1 (B1)", callback_data="select_level:B1"),
            InlineKeyboardButton(text="🇧2 (B2)", callback_data="select_level:B2")
        ],
        [
            InlineKeyboardButton(text="🇨1 (C1)", callback_data="select_level:C1"),
            InlineKeyboardButton(text="🇨2 (C2)", callback_data="select_level:C2")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def lessons_keyboard(level: str) -> InlineKeyboardMarkup:
    """Berilgan darajadagi 12 ta dars inline klaviaturasi."""
    keyboard = []
    # 12 ta darsni 3 tadan qilib joylashtiramiz
    for row_idx in range(0, 12, 3):
        row = []
        for col_idx in range(1, 4):
            lesson_num = row_idx + col_idx
            row.append(
                InlineKeyboardButton(
                    text=f"{lesson_num}-dars",
                    callback_data=f"select_lesson:{level}:{lesson_num}"
                )
            )
        keyboard.append(row)
    
    # Orqaga qaytish tugmasi
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Darajalarga qaytish", callback_data="back_to_levels")
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_levels_keyboard() -> InlineKeyboardMarkup:
    """Admin uchun darajalar inline klaviaturasi."""
    keyboard = [
        [
            InlineKeyboardButton(text="🇦1 (A1)", callback_data="admin_level:A1"),
            InlineKeyboardButton(text="🇦2 (A2)", callback_data="admin_level:A2")
        ],
        [
            InlineKeyboardButton(text="🇧1 (B1)", callback_data="admin_level:B1"),
            InlineKeyboardButton(text="🇧2 (B2)", callback_data="admin_level:B2")
        ],
        [
            InlineKeyboardButton(text="🇨1 (C1)", callback_data="admin_level:C1"),
            InlineKeyboardButton(text="🇨2 (C2)", callback_data="admin_level:C2")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_lessons_keyboard(level: str) -> InlineKeyboardMarkup:
    """Admin uchun berilgan darajadagi 12 ta dars inline klaviaturasi."""
    keyboard = []
    # 12 ta darsni 3 tadan qilib joylashtiramiz
    for row_idx in range(0, 12, 3):
        row = []
        for col_idx in range(1, 4):
            lesson_num = row_idx + col_idx
            row.append(
                InlineKeyboardButton(
                    text=f"{lesson_num}-dars",
                    callback_data=f"admin_lesson:{level}:{lesson_num}"
                )
            )
        keyboard.append(row)
    
    # Orqaga qaytish tugmasi
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Darajalarga qaytish", callback_data="admin_back_to_levels")
    ])
    return InlineKeyboardMarkup(keyboard)


def lesson_menu_keyboard(level: str, lesson_num: int, lesson_id: int) -> InlineKeyboardMarkup:
    """O'quvchi darsni tanlaganda chiqadigan dars menyusi."""
    keyboard = [
        [InlineKeyboardButton(
            text="📹 Video darsni ko'rish",
            callback_data=f"view_video:{level}:{lesson_num}"
        )]
    ]
    
    # Faqat A1 va A2 darajalari uchun o'qilishini (audio) tinglash tugmasini qo'shamiz
    if level.upper() in ["A1", "A2"]:
        keyboard.append([InlineKeyboardButton(
            text="🔊 O'qilishini tinglash (Audio)",
            callback_data=f"view_audio:{level}:{lesson_num}"
        )])

    keyboard.extend([
        [InlineKeyboardButton(
            text="📖 Lug'atni o'qish (Yodlash)",
            callback_data=f"view_vocab_words:{level}:{lesson_num}"
        )],
        [InlineKeyboardButton(
            text="✍️ Testni topshirish",
            callback_data=f"start_quiz:{lesson_id}"
        )],
        [InlineKeyboardButton(
            text="⬅️ Darslar ro'yxatiga qaytish",
            callback_data=f"select_level:{level}"
        )]
    ])
    return InlineKeyboardMarkup(keyboard)


def back_to_lesson_menu_keyboard(level: str, lesson_num: int) -> InlineKeyboardMarkup:
    """Video darslik yoki lug'at ko'rilganda, dars menyusiga qaytish tugmasi."""
    keyboard = [
        [InlineKeyboardButton(
            text="⬅️ Dars bo'limlariga qaytish",
            callback_data=f"back_to_lesson:{level}:{lesson_num}"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Bekor qilish (Orqaga) reply klaviaturasi."""
    keyboard = [[KeyboardButton(text="Bekor qilish")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    """Klaviaturani olib tashlash."""
    return ReplyKeyboardRemove()
