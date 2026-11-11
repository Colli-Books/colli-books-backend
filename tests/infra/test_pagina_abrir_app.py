"""Página `/abrir/...`: ponte entre o link https do e-mail e o app (US02, US04)."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.links import build_app_link

TOKEN = "AbC123_-xyz7890qwertyUIOP"


@pytest.mark.parametrize(
    ("destino", "deep_link"),
    [
        ("convite", f"collibooks://convite?token={TOKEN}"),
        ("redefinir-senha", f"collibooks://redefinir-senha?token={TOKEN}"),
    ],
)
def test_pagina_tem_botao_que_abre_o_app(client: TestClient, destino: str, deep_link: str) -> None:
    response = client.get(f"/abrir/{destino}", params={"token": TOKEN})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert f'href="{deep_link}"' in response.text


def test_convite_mostra_codigo_para_colar_no_app(client: TestClient) -> None:
    response = client.get("/abrir/convite", params={"token": TOKEN})

    assert f'<code id="code">{TOKEN}</code>' in response.text
    assert "Tenho um convite" in response.text


def test_redefinicao_nao_mostra_codigo(client: TestClient) -> None:
    response = client.get("/abrir/redefinir-senha", params={"token": TOKEN})

    assert 'id="code"' not in response.text


def test_pagina_nao_e_cacheada_nem_vaza_o_token(client: TestClient) -> None:
    response = client.get("/abrir/convite", params={"token": TOKEN})

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize(
    ("destino", "token"),
    [
        ("convite", ""),
        ("convite", "curto"),
        ("convite", '"><script>alert(1)</script>xxxxxxxx'),
        ("outra-coisa", TOKEN),
    ],
)
def test_link_adulterado_mostra_erro_sem_refletir_a_entrada(
    client: TestClient, destino: str, token: str
) -> None:
    response = client.get(f"/abrir/{destino}", params={"token": token})

    assert response.status_code == 404
    assert "Link inválido" in response.text
    assert "<script>alert" not in response.text
    assert "collibooks://" not in response.text


def test_link_do_email_aponta_para_a_pagina_quando_a_base_e_https(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(get_settings(), "app_link_base_url", "https://api.exemplo.com/abrir")

    link = build_app_link("convite", TOKEN)

    assert link == f"https://api.exemplo.com/abrir/convite?token={TOKEN}"
    path = link.removeprefix("https://api.exemplo.com")
    assert client.get(path).status_code == 200


def test_esquema_do_app_vem_da_configuracao(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(get_settings(), "app_scheme", "colliteste")

    response = client.get("/abrir/convite", params={"token": TOKEN})

    assert f'href="colliteste://convite?token={TOKEN}"' in response.text
