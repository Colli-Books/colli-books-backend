"""Utilidades compartilhadas entre as views."""


def blank_to_none(value: str | None) -> str | None:
    """Texto vazio ou só de espaços vira `None` — usado em campos opcionais."""
    if value is None:
        return None
    return value.strip() or None
