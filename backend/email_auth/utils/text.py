"""Normalización de texto/correo y escape seguro para HTML."""
import re

from django.utils.html import escape

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_PATTERN.match(email or ""))


def escape_html(value) -> str:
    return escape("" if value is None else str(value))


def text_to_html(value: str) -> str:
    return escape_html(value).replace("\r\n", "\n").replace("\n", "<br>")
