"""
SQLAlchemy ORM modellari.
Jadvallar: User, Lesson, Word, UserProgress.
"""
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float,
    ForeignKey, Integer, String, Text, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    """Hozirgi UTC vaqtini qaytaradi."""
    return datetime.now(timezone.utc)


class User(Base):
    """
    Telegram foydalanuvchilari jadvali.
    Har bir foydalanuvchi birinchi /start bosganda yoziladi.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    fullname: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Munosabatlar
    progress: Mapped[List["UserProgress"]] = relationship(
        "UserProgress", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} fullname={self.fullname!r}>"


class Lesson(Base):
    """
    Darslar jadvali. Admin .txt fayl yuklasa, yangi dars yaratiladi.
    """
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="A1", index=True) # A1, A2, B1, B2, C1, C2
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Munosabatlar
    words: Mapped[List["Word"]] = relationship(
        "Word", back_populates="lesson", cascade="all, delete-orphan"
    )
    progress: Mapped[List["UserProgress"]] = relationship(
        "UserProgress", back_populates="lesson", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lesson id={self.id} title={self.title!r}>"


class Word(Base):
    """
    So'zlar jadvali. Har bir so'z bitta darsga tegishli.
    Format: english_word | pronunciation | uzbek_translation
    """
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lesson_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    english_word: Mapped[str] = mapped_column(String(255), nullable=False)
    pronunciation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    uzbek_translation: Mapped[str] = mapped_column(String(500), nullable=False)

    # Munosabatlar
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="words")

    def __repr__(self) -> str:
        return f"<Word id={self.id} english={self.english_word!r}>"


class UserProgress(Base):
    """
    Foydalanuvchi progress jadvali.
    Har bir test yakunlanganida yangi yozuv qo'shiladi.
    """
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    wrong_words: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="Xato qilingan so'zlar: [{'word': '...', 'correct': '...', 'given': '...'}]"
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Munosabatlar
    user: Mapped["User"] = relationship("User", back_populates="progress")
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="progress")

    def __repr__(self) -> str:
        return f"<UserProgress user_id={self.user_id} lesson_id={self.lesson_id} score={self.score_percentage}%>"
