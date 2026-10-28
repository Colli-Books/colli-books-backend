"""Casos de redefinição de senha compartilhados pela US04 (professor) e US06 (admin)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PasswordResetToken, User, UserRole, UserStatus
from app.security.tokens import hash_token
from app.services.email import EmailKind
from tests.factories import DEFAULT_PASSWORD, create_user
from tests.fakes import InMemoryEmailSender

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
EMAIL = "conta@colli.com"
NEW_PASSWORD = "minha-senha-nova"


def _request_token(client: TestClient, outbox: InMemoryEmailSender) -> str:
    client.post(FORGOT, json={"email": EMAIL})
    return outbox.outbox[-1].params["code"]


def _login(client: TestClient, password: str):
    return client.post(LOGIN, json={"email": EMAIL, "password": password})


def _reset(client: TestClient, token: str, password: str = NEW_PASSWORD):
    return client.post(RESET, json={"token": token, "new_password": password})


def _token_ja_usado(client: TestClient, db: Session, outbox: InMemoryEmailSender) -> str:
    token = _request_token(client, outbox)
    _reset(client, token)
    return token


def _token_expirado(client: TestClient, db: Session, outbox: InMemoryEmailSender) -> str:
    token = _request_token(client, outbox)
    stored = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    return token


def _token_substituido(client: TestClient, db: Session, outbox: InMemoryEmailSender) -> str:
    old = _request_token(client, outbox)
    _request_token(client, outbox)
    return old


def _token_inventado(client: TestClient, db: Session, outbox: InMemoryEmailSender) -> str:
    return "inventado"


class RedefinicaoSenha:
    """Critérios de aceitação comuns; a subclasse define `role`."""

    role: UserRole

    @pytest.fixture()
    def user(self, db_session: Session) -> User:
        return create_user(db_session, email=EMAIL, role=self.role)

    @pytest.mark.parametrize("email", [EMAIL, "CONTA@colli.com", "Conta@Colli.COM"])
    def test_pedido_envia_link_de_redefinicao_com_validade(
        self, client: TestClient, user: User, email_outbox: InMemoryEmailSender, email: str
    ) -> None:
        response = client.post(FORGOT, json={"email": email})

        assert response.status_code == 202
        [message] = email_outbox.outbox
        assert message.to == EMAIL
        assert message.kind == EmailKind.PASSWORD_RESET
        assert message.params["link"].startswith("collibooks://redefinir-senha?token=")
        assert message.params["code"]
        assert message.params["ttl_minutes"] == "30"

    @pytest.mark.parametrize("missing", ["ninguem@colli.com", "outra@escola.com"])
    def test_resposta_e_identica_para_email_existente_e_inexistente(
        self, client: TestClient, user: User, email_outbox: InMemoryEmailSender, missing: str
    ) -> None:
        existing = client.post(FORGOT, json={"email": EMAIL})
        absent = client.post(FORGOT, json={"email": missing})

        assert existing.status_code == absent.status_code == 202
        assert existing.json() == absent.json()
        assert len(email_outbox.outbox) == 1

    @pytest.mark.parametrize(
        ("status", "password"),
        [(UserStatus.INVITE_PENDING, None), (UserStatus.INACTIVE, DEFAULT_PASSWORD)],
        ids=["convite-pendente", "inativa"],
    )
    def test_conta_nao_ativa_e_ignorada_em_silencio(
        self,
        client: TestClient,
        db_session: Session,
        email_outbox: InMemoryEmailSender,
        status: UserStatus,
        password: str | None,
    ) -> None:
        create_user(db_session, email=EMAIL, role=self.role, status=status, password=password)

        response = client.post(FORGOT, json={"email": EMAIL})

        assert response.status_code == 202
        assert email_outbox.outbox == []

    @pytest.mark.parametrize(
        ("password", "status_code"), [(NEW_PASSWORD, 200), (DEFAULT_PASSWORD, 401)]
    )
    def test_redefinir_troca_a_senha(
        self,
        client: TestClient,
        user: User,
        email_outbox: InMemoryEmailSender,
        password: str,
        status_code: int,
    ) -> None:
        token = _request_token(client, email_outbox)

        assert _reset(client, token).status_code == 204
        assert _login(client, password).status_code == status_code

    def test_redefinir_encerra_todas_as_sessoes(
        self, client: TestClient, user: User, email_outbox: InMemoryEmailSender
    ) -> None:
        refresh = _login(client, DEFAULT_PASSWORD).json()["refresh_token"]
        token = _request_token(client, email_outbox)

        _reset(client, token)

        assert client.post(REFRESH, json={"refresh_token": refresh}).status_code == 401

    @pytest.mark.parametrize(
        "cenario",
        [
            pytest.param(_token_ja_usado, id="ja-usado"),
            pytest.param(_token_expirado, id="expirado"),
            pytest.param(_token_substituido, id="substituido-por-novo-pedido"),
            pytest.param(_token_inventado, id="inventado"),
        ],
    )
    def test_link_invalido_e_recusado(
        self,
        client: TestClient,
        db_session: Session,
        user: User,
        email_outbox: InMemoryEmailSender,
        cenario: Callable[[TestClient, Session, InMemoryEmailSender], str],
    ) -> None:
        token = cenario(client, db_session, email_outbox)

        response = _reset(client, token, "outra-senha-999")

        assert response.status_code == 400
        assert response.json()["code"] == "RESET_TOKEN_INVALID"

    def test_novo_pedido_vale_no_lugar_do_anterior(
        self, client: TestClient, user: User, email_outbox: InMemoryEmailSender
    ) -> None:
        _request_token(client, email_outbox)
        new = _request_token(client, email_outbox)

        assert _reset(client, new).status_code == 204

    @pytest.mark.parametrize("weak", ["", "curta", "1234567", "a" * 129])
    def test_senha_fraca_nao_consome_o_token(
        self, client: TestClient, user: User, email_outbox: InMemoryEmailSender, weak: str
    ) -> None:
        token = _request_token(client, email_outbox)

        response = _reset(client, token, weak)

        assert response.status_code == 422
        assert response.json()["code"] == "WEAK_PASSWORD"
        assert _reset(client, token).status_code == 204
