"""US01 — Cadastro de professor pelo administrador."""

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.main import app
from app.models import Invite, User, UserStatus
from app.security.tokens import hash_token
from app.services import email as email_service
from app.services.email import (
    BackgroundEmailSender,
    BrevoEmailSender,
    ConsoleEmailSender,
    EmailKind,
    EmailMessage,
    EmailSender,
    _safe_send,
    get_email_sender,
)
from app.services.links import build_app_link
from tests.factories import DEFAULT_PASSWORD, auth_headers, create_user
from tests.fakes import InMemoryEmailSender

TEACHERS = "/api/v1/admin/teachers"
LOGIN = "/api/v1/auth/login"

_MESSAGE = EmailMessage(
    to="p@escola.com",
    kind=EmailKind.INVITE,
    params={"link": "collibooks://x?token=t", "code": "t", "expires_at": "25/10/2026 14:00 (UTC)"},
)


def _create(client: TestClient, admin: User, email: str = "novo@escola.com"):
    return client.post(TEACHERS, json={"email": email}, headers=auth_headers(admin))


class _FakeBrevoClient:
    """Finge o cliente do SDK: registra as chamadas de envio."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def transactional_emails(self) -> "_FakeBrevoClient":
        return self

    def send_transac_email(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _FailingSender:
    """Provê `send` que sempre falha, como um provedor fora do ar."""

    def send(self, message: EmailMessage) -> None:
        raise RuntimeError("provedor fora do ar")


@pytest.mark.parametrize("email", ["novo@escola.com", "Novo@Escola.com", "NOVO@ESCOLA.COM"])
def test_admin_cadastra_professor_com_convite_pendente(
    client: TestClient, db_session: Session, admin_user: User, email: str
) -> None:
    response = _create(client, admin_user, email)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "novo@escola.com"
    assert body["status"] == "invite_pending"

    link = urlparse(body["invite_link"])
    assert (link.scheme, link.netloc) == ("collibooks", "convite")
    assert parse_qs(link.query)["token"] == [body["invite_code"]]

    expires_at = datetime.fromisoformat(body["invite_expires_at"])
    assert expires_at.tzinfo is not None
    assert timedelta(hours=71) < expires_at - datetime.now(UTC) <= timedelta(hours=72)

    user = db_session.get(User, body["id"])
    assert user.password_hash is None
    invite = db_session.scalar(select(Invite).where(Invite.user_id == user.id))
    assert invite.token_hash == hash_token(body["invite_code"])


@pytest.mark.parametrize("param", ["link", "code"])
def test_cadastro_manda_o_convite_para_o_email_do_professor(
    client: TestClient, admin_user: User, email_outbox: InMemoryEmailSender, param: str
) -> None:
    body = _create(client, admin_user, "Novo@Escola.com").json()

    [message] = email_outbox.outbox
    assert message.to == "novo@escola.com"
    assert message.kind == EmailKind.INVITE
    assert message.params[param] == body[f"invite_{param}"]
    assert message.params["expires_at"]


@pytest.mark.parametrize("duplicate", ["dup@escola.com", "DUP@escola.com", "Dup@Escola.Com"])
def test_email_duplicado_responde_409_e_nao_manda_email(
    client: TestClient, admin_user: User, email_outbox: InMemoryEmailSender, duplicate: str
) -> None:
    _create(client, admin_user, "dup@escola.com")
    email_outbox.outbox.clear()

    response = _create(client, admin_user, duplicate)

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_ALREADY_REGISTERED"
    assert email_outbox.outbox == []


@pytest.mark.parametrize("email", ["nao-e-email", "", "sem-arroba.com", "a@"])
def test_email_invalido_responde_422(client: TestClient, admin_user: User, email: str) -> None:
    response = _create(client, admin_user, email)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_falha_no_envio_do_email_nao_quebra_a_resposta(
    client: TestClient, admin_user: User, caplog: pytest.LogCaptureFixture
) -> None:
    """O envio é em background: um provedor fora do ar não muda o contrato (201)."""

    def _failing(background_tasks: BackgroundTasks) -> EmailSender:
        return BackgroundEmailSender(background_tasks, _FailingSender())

    app.dependency_overrides[get_email_sender] = _failing

    with caplog.at_level(logging.ERROR, logger="app.services.email"):
        response = _create(client, admin_user, "falha@escola.com")

    assert response.status_code == 201
    assert response.json()["invite_link"]
    assert "Falha ao enviar e-mail para falha@escola.com (tipo=invite)" in caplog.text


@pytest.mark.parametrize(
    ("requester", "status_code", "code"),
    [(None, 401, "UNAUTHENTICATED"), ("teacher_user", 403, "FORBIDDEN")],
    ids=["anonimo", "professor"],
)
def test_so_admin_cadastra_professor(
    request: pytest.FixtureRequest,
    client: TestClient,
    requester: str | None,
    status_code: int,
    code: str,
) -> None:
    headers = auth_headers(request.getfixturevalue(requester)) if requester else {}

    response = client.post(TEACHERS, json={"email": "novo@escola.com"}, headers=headers)

    assert response.status_code == status_code
    assert response.json()["code"] == code


@pytest.mark.parametrize("password", ["qualquer-123", DEFAULT_PASSWORD])
def test_convidado_nao_consegue_fazer_login(
    client: TestClient, admin_user: User, password: str
) -> None:
    _create(client, admin_user, "convidado@escola.com")

    response = client.post(LOGIN, json={"email": "convidado@escola.com", "password": password})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_novo_convite_substitui_o_anterior_e_vai_por_email(
    client: TestClient, db_session: Session, admin_user: User, email_outbox: InMemoryEmailSender
) -> None:
    first = _create(client, admin_user).json()
    email_outbox.outbox.clear()

    response = client.post(f"{TEACHERS}/{first['id']}/invite", headers=auth_headers(admin_user))

    assert response.status_code == 200
    assert response.json()["invite_code"] != first["invite_code"]
    hashes = db_session.scalars(select(Invite.token_hash).where(Invite.user_id == first["id"]))
    assert list(hashes) == [hash_token(response.json()["invite_code"])]
    [message] = email_outbox.outbox
    assert message.to == first["email"]
    assert message.kind == EmailKind.INVITE_RENEWAL
    assert message.params["link"] == response.json()["invite_link"]


@pytest.mark.parametrize(
    ("target", "status_code", "code"),
    [
        ("ativo", 409, "ACCOUNT_ALREADY_ACTIVE"),
        ("inexistente", 404, None),
        ("admin", 404, None),
    ],
)
def test_novo_convite_recusado(
    client: TestClient,
    admin_user: User,
    teacher_user: User,
    target: str,
    status_code: int,
    code: str | None,
) -> None:
    user_id = {"ativo": teacher_user.id, "inexistente": 999_999, "admin": admin_user.id}[target]

    response = client.post(f"{TEACHERS}/{user_id}/invite", headers=auth_headers(admin_user))

    assert response.status_code == status_code
    if code:
        assert response.json()["code"] == code


def test_professor_nao_gera_convite(client: TestClient, db_session: Session) -> None:
    pending = create_user(db_session, status=UserStatus.INVITE_PENDING, password=None)
    teacher = create_user(db_session)

    response = client.post(f"{TEACHERS}/{pending.id}/invite", headers=auth_headers(teacher))

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("collibooks://", "collibooks://convite?token=abc-123"),
        ("https://colli.com.br", "https://colli.com.br/convite?token=abc-123"),
        ("https://colli.com.br/app/", "https://colli.com.br/app/convite?token=abc-123"),
    ],
)
def test_monta_link_do_convite_a_partir_da_base(
    monkeypatch: pytest.MonkeyPatch, base: str, expected: str
) -> None:
    monkeypatch.setattr(get_settings(), "app_link_base_url", base)

    assert build_app_link("convite", "abc-123") == expected


@pytest.mark.parametrize("trecho", ["p@escola.com", "invite", "collibooks://x?token=t"])
def test_sem_provedor_o_email_vai_para_o_log(caplog: pytest.LogCaptureFixture, trecho: str) -> None:
    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        ConsoleEmailSender().send(_MESSAGE)

    assert trecho in caplog.text


def test_em_producao_o_log_nao_expoe_os_params(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    get_settings.cache_clear()
    try:
        with caplog.at_level(logging.WARNING, logger="app.services.email"):
            ConsoleEmailSender().send(_MESSAGE)
    finally:
        get_settings.cache_clear()

    assert "p@escola.com" in caplog.text
    assert "token=t" not in caplog.text


@pytest.mark.parametrize(
    ("kind", "template_id"),
    [(EmailKind.INVITE, 7), (EmailKind.INVITE_RENEWAL, 8), (EmailKind.PASSWORD_RESET, 9)],
)
def test_brevo_usa_o_template_do_kind_e_passa_os_params(kind: EmailKind, template_id: int) -> None:
    client = _FakeBrevoClient()
    sender = BrevoEmailSender(client, {kind: template_id})
    message = EmailMessage(to="p@escola.com", kind=kind, params=_MESSAGE.params)

    sender.send(message)

    [call] = client.calls
    assert call["template_id"] == template_id
    assert [to.email for to in call["to"]] == ["p@escola.com"]
    assert call["params"] == _MESSAGE.params


@pytest.mark.parametrize("kind", list(EmailKind))
def test_brevo_sem_template_configurado_falha(kind: EmailKind) -> None:
    sender = BrevoEmailSender(_FakeBrevoClient(), {kind: 0})
    message = EmailMessage(to="p@escola.com", kind=kind, params={})

    with pytest.raises(RuntimeError, match=kind.value):
        sender.send(message)


def test_background_enfileira_o_envio() -> None:
    tasks = BackgroundTasks()
    client = _FakeBrevoClient()
    sender = BackgroundEmailSender(tasks, BrevoEmailSender(client, {EmailKind.INVITE: 7}))

    sender.send(_MESSAGE)

    [task] = tasks.tasks
    assert task.func is _safe_send
    assert client.calls == []
    task.func(*task.args, **task.kwargs)
    [call] = client.calls
    assert call["params"] == _MESSAGE.params


def test_safe_send_loga_a_falha_e_nao_propaga(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="app.services.email"):
        _safe_send(_FailingSender(), _MESSAGE)

    assert "Falha ao enviar e-mail para p@escola.com (tipo=invite)" in caplog.text
    assert "provedor fora do ar" in caplog.text
    assert "token=t" not in caplog.text


def test_get_email_sender_envolve_o_default_em_background(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tasks = BackgroundTasks()
    sender = get_email_sender(tasks)

    assert isinstance(sender, BackgroundEmailSender)
    sender.send(_MESSAGE)

    [task] = tasks.tasks
    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        task.func(*task.args, **task.kwargs)
    assert "p@escola.com" in caplog.text


@pytest.mark.parametrize(
    ("api_key", "expected"), [("xkeys", BrevoEmailSender), ("", ConsoleEmailSender)]
)
def test_default_sender_depende_da_api_key(
    monkeypatch: pytest.MonkeyPatch, api_key: str, expected: type
) -> None:
    monkeypatch.setenv("BREVO_API_KEY", api_key)
    monkeypatch.setattr(email_service, "Brevo", lambda api_key: _FakeBrevoClient())
    get_settings.cache_clear()
    email_service._default_sender.cache_clear()
    try:
        assert isinstance(email_service._default_sender(), expected)
    finally:
        get_settings.cache_clear()
        email_service._default_sender.cache_clear()


@pytest.mark.parametrize(
    ("field", "default"),
    [
        ("brevo_api_key", ""),
        ("brevo_template_invite", 0),
        ("brevo_template_invite_renewal", 0),
        ("brevo_template_password_reset", 0),
    ],
)
def test_configuracoes_do_brevo_tem_defaults_neutros(field: str, default: object) -> None:
    """Sem chave, o e-mail cai no log; sem template, o envio com Brevo falha no log."""
    assert Settings.model_fields[field].default == default
