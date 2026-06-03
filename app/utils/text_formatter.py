"""
Matnlarni formatlash va tozalash bo'yicha yordamchi funksiyalar.
"""
import re


def escape_html(text: str) -> str:
    """
    Telegram HTML formatlashi uchun maxsus belgilarni tozalaydi.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def clean_pronunciation(pron: str) -> str:
    """
    Talaffuz qavslarini tozalaydi va bir xil ko'rinishga keltiradi.
    Misol: '[ˈæktʃuəli]' -> '[ˈæktʃuəli]'
    """
    if not pron:
        return ""
    pron = pron.strip()
    if not pron.startswith("["):
        pron = "[" + pron
    if not pron.endswith("]"):
        pron = pron + "]"
    return pron
