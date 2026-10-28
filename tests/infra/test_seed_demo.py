"""Seed de demonstração (`python -m app.cli seed-demo`): idempotente e completo."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, EducationLevel, InstitutionalPage, Theme
from app.services.demo_seed import (
    BOOKS,
    EDUCATION_LEVELS,
    INSTITUTIONAL_PAGES,
    THEMES,
    seed_demo,
)


def test_seed_demo_popula_tudo(db_session: Session) -> None:
    report = seed_demo(db_session)

    assert report.themes_created == len(THEMES)
    assert report.education_levels_created == len(EDUCATION_LEVELS)
    assert report.books_created == len(BOOKS)
    assert report.institutional_pages_created == len(INSTITUTIONAL_PAGES)

    aurora = db_session.scalar(select(Book).where(Book.isbn == "978-65-6079-046-9"))
    assert aurora.title == "O Segredo de Aurora"
    assert aurora.education_level.name == "Educação Infantil"
    assert {t.name for t in aurora.themes} >= {"Inclusão", "Diversidade", "Empatia"}


def test_seed_demo_e_idempotente(db_session: Session) -> None:
    seed_demo(db_session)
    report = seed_demo(db_session)

    assert report.themes_created == 0
    assert report.education_levels_created == 0
    assert report.books_created == 0
    assert report.institutional_pages_created == 0

    counts = (
        db_session.scalar(select(func.count(Theme.id))),
        db_session.scalar(select(func.count(EducationLevel.id))),
        db_session.scalar(select(func.count(Book.id))),
        db_session.scalar(select(func.count(InstitutionalPage.id))),
    )
    assert counts == (len(THEMES), len(EDUCATION_LEVELS), len(BOOKS), len(INSTITUTIONAL_PAGES))


def test_seed_reaproveita_tema_preexistente_ignorando_caixa(db_session: Session) -> None:
    """Um tema cadastrado pelo admin (com caixa diferente) é reaproveitado."""
    db_session.add(Theme(name="empatia"))
    db_session.flush()

    report = seed_demo(db_session)

    assert report.themes_created == len(THEMES) - 1
    assert db_session.scalar(select(func.count(Theme.id))) == len(THEMES)
