"""US18 — Navegação com seções institucionais."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstitutionalPage
from app.services.demo_seed import seed_demo

MENU = ["Home", "Editora", "PNLD", "Catálogo", "Blog", "Anima Kids", "Contato"]


@pytest.mark.parametrize("title", MENU)
def test_cada_secao_do_menu_tem_pagina_pre_cadastrada(db_session: Session, title: str) -> None:
    seed_demo(db_session)

    page = db_session.scalar(select(InstitutionalPage).where(InstitutionalPage.title == title))

    assert page is not None
    assert page.external_url.startswith("https://")


def test_secoes_seguem_a_ordem_do_menu(db_session: Session) -> None:
    seed_demo(db_session)

    titles = db_session.scalars(
        select(InstitutionalPage.title).order_by(InstitutionalPage.sort_order)
    ).all()

    assert titles == MENU
