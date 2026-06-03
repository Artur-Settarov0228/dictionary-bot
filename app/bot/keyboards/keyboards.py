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


def remove_keyboard() -> ReplyKeyboardRemove:
    """Klaviaturani olib tashlash."""
    return ReplyKeyboardRemove()
