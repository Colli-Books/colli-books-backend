"""US02 — Primeiro acesso e conclusão do cadastro."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, ErrorCode
from app.models import Invite, User, UserStatus
from app.security.passwords import hash_password, validate_password_strength, verify_password
from app.security.tokens import hash_token
from app.services.email import EmailKind
from app.services.invites import issue_invite
from tests.factories import create_user
from tests.fakes import InMemoryEmailSender

VERIFY = "/api/v1/invites/verify"
ACCEPT = "/api/v1/invites/accept"
RESEND = "/api/v1/invites/resend"
LOGIN = "/api/v1/auth/login"
NEW_PASSWORD = "minha-senha-nova"


def _accept(token: str, password: str = NEW_PASSWORD, **profile: str | None) -> dict:
    """Corpo de `/invites/accept`; `profile` sobrescreve nome e escola."""
    return {"token": token, "full_name": "Maria Souza", "password": password, **profile}


@pytest.fixture()
def pending_user(db_session: Session) -> User:
    return create_user(
        db_session, email="convidado@escola.com", status=UserStatus.INVITE_PENDING, password=None
    )


@pytest.fixture()
def invite_code(db_session: Session, pending_user: User) -> str:
    code = issue_invite(db_session, pending_user).code
    db_session.flush()
    return code


def _expire(db_session: Session, code: str) -> None:
    invite = db_session.scalar(select(Invite).where(Invite.token_hash == hash_token(code)))
    invite.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()


def _inexistente(client: TestClient, db_session: Session, user: User, code: str) -> str:
    return "inventado"


def _expirado(client: TestClient, db_session: Session, user: User, code: str) -> str:
    _expire(db_session, code)
    return code


def _usado(client: TestClient, db_session: Session, user: User, code: str) -> str:
    client.post(ACCEPT, json=_accept(code))
    return code


def _conta_desativada(client: TestClient, db_session: Session, user: User, code: str) -> str:
    user.status = UserStatus.INACTIVE
    db_session.flush()
    return code


Cenario = Callable[[TestClient, Session, User, str], str]

CONVITES_INUTILIZAVEIS = [
    pytest.param(_inexistente, 404, "INVITE_INVALID", id="inexistente"),
    pytest.param(_expirado, 410, "INVITE_EXPIRED", id="expirado"),
    pytest.param(_usado, 409, "INVITE_ALREADY_USED", id="ja-usado"),
    pytest.param(_conta_desativada, 404, "INVITE_INVALID", id="conta-desativada"),
]


def test_verificar_convite_valido_devolve_o_email(client: TestClient, invite_code: str) -> None:
    response = client.post(VERIFY, json={"token": invite_code})

    assert response.status_code == 200
    assert response.json() == {"email": "convidado@escola.com"}


@pytest.mark.parametrize("path", [VERIFY, ACCEPT], ids=["verificar", "aceitar"])
@pytest.mark.parametrize(("cenario", "status_code", "code"), CONVITES_INUTILIZAVEIS)
def test_convite_inutilizavel_e_recusado(
    client: TestClient,
    db_session: Session,
    pending_user: User,
    invite_code: str,
    path: str,
    cenario: Cenario,
    status_code: int,
    code: str,
) -> None:
    token = cenario(client, db_session, pending_user, invite_code)

    response = client.post(path, json=_accept(token, "outra-senha-999"))

    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_aceitar_completa_cadastro_ativa_conta_e_autentica(
    client: TestClient, db_session: Session, pending_user: User, invite_code: str
) -> None:
    response = client.post(
        ACCEPT, json=_accept(invite_code, full_name="  Maria Souza ", school="E.E. Machado")
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["status"] == "active"
    assert body["user"]["full_name"] == "Maria Souza"
    assert body["user"]["school"] == "E.E. Machado"
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200

    db_session.refresh(pending_user)
    assert pending_user.status == UserStatus.ACTIVE
    assert (pending_user.full_name, pending_user.school) == ("Maria Souza", "E.E. Machado")
    invite = db_session.scalar(select(Invite).where(Invite.user_id == pending_user.id))
    assert invite.used_at is not None


@pytest.mark.parametrize(("password", "status_code"), [(NEW_PASSWORD, 200), ("outra-senha", 401)])
def test_depois_de_aceitar_faz_login_so_com_a_senha_nova(
    client: TestClient, invite_code: str, password: str, status_code: int
) -> None:
    client.post(ACCEPT, json=_accept(invite_code))

    response = client.post(LOGIN, json={"email": "convidado@escola.com", "password": password})

    assert response.status_code == status_code


@pytest.mark.parametrize("password", ["", "1234567", "a" * 129])
def test_senha_fora_das_regras_responde_weak_password_e_nao_consome_o_convite(
    client: TestClient, invite_code: str, password: str
) -> None:
    response = client.post(ACCEPT, json=_accept(invite_code, password))

    assert response.status_code == 422
    assert response.json()["code"] == "WEAK_PASSWORD"
    assert client.post(VERIFY, json={"token": invite_code}).status_code == 200


@pytest.mark.parametrize("school", [None, "", "   "])
def test_escola_e_opcional(client: TestClient, invite_code: str, school: str | None) -> None:
    response = client.post(ACCEPT, json=_accept(invite_code, school=school))

    assert response.status_code == 200
    assert response.json()["user"]["school"] is None


@pytest.mark.parametrize("full_name", [None, "", "   ", "x" * 256])
def test_nome_obrigatorio_e_nao_consome_o_convite(
    client: TestClient, invite_code: str, full_name: str | None
) -> None:
    body = _accept(invite_code)
    if full_name is None:
        del body["full_name"]
    else:
        body["full_name"] = full_name

    response = client.post(ACCEPT, json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert client.post(VERIFY, json={"token": invite_code}).status_code == 200


def test_reenviar_convite_expirado_manda_link_novo_por_email(
    client: TestClient, db_session: Session, invite_code: str, email_outbox: InMemoryEmailSender
) -> None:
    _expire(db_session, invite_code)

    response = client.post(RESEND, json={"token": invite_code})

    assert response.status_code == 202
    assert invite_code not in response.text
    [message] = email_outbox.outbox
    assert message.to == "convidado@escola.com"
    assert message.kind == EmailKind.INVITE_RENEWAL
    assert message.params["link"].startswith("collibooks://convite?token=")

    new_code = message.params["code"]
    assert client.post(VERIFY, json={"token": new_code}).status_code == 200
    assert client.post(VERIFY, json={"token": invite_code}).json()["code"] == "INVITE_INVALID"


def _valido(client: TestClient, db_session: Session, user: User, code: str) -> str:
    return code


@pytest.mark.parametrize(
    "cenario",
    [
        pytest.param(_valido, id="ainda-valido"),
        pytest.param(_usado, id="ja-usado"),
        pytest.param(_inexistente, id="inexistente"),
    ],
)
def test_reenviar_fora_do_caso_expirado_nao_faz_nada(
    client: TestClient,
    db_session: Session,
    pending_user: User,
    invite_code: str,
    email_outbox: InMemoryEmailSender,
    cenario: Cenario,
) -> None:
    token = cenario(client, db_session, pending_user, invite_code)
    expected = client.post(RESEND, json={"token": "outro-inventado"}).json()

    response = client.post(RESEND, json={"token": token})

    assert response.status_code == 202
    assert response.json() == expected
    assert email_outbox.outbox == []


def test_hash_nao_guarda_a_senha_em_claro() -> None:
    hashed = hash_password("senha-segura-123")

    assert "senha-segura-123" not in hashed
    assert hashed.startswith("$argon2")


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [("senha-segura-123", True), ("senha-errada-123", False), ("", False)],
)
def test_verifica_senha_contra_o_hash(attempt: str, expected: bool) -> None:
    assert verify_password(attempt, hash_password("senha-segura-123")) is expected


def test_mesma_senha_gera_hashes_diferentes() -> None:
    assert hash_password("senha-segura-123") != hash_password("senha-segura-123")


def test_sem_hash_a_verificacao_sempre_falha() -> None:
    assert verify_password("qualquer-coisa", None) is False


@pytest.mark.parametrize("password", ["12345678", "a" * 128])
def test_aceita_senha_dentro_dos_limites(password: str) -> None:
    validate_password_strength(password)


@pytest.mark.parametrize("password", ["", "1234567", "a" * 129])
def test_rejeita_senha_fora_dos_limites(password: str) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_password_strength(password)

    assert exc_info.value.code == ErrorCode.WEAK_PASSWORD
    assert exc_info.value.status_code == 422
