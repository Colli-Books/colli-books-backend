"""Perfil e Minha Seleção do usuário logado (US10–US12).

Todos os endpoints agem sobre o dono do access token — nenhum recebe id de
usuário de fora (correção sobre o desenho original, seção 9 do contrato).
"""

from fastapi import APIRouter, Response, status

from app.security.dependencies import CurrentUser, DbSession
from app.services import profile as profile_service
from app.views.books import BookSummary
from app.views.catalog import EducationLevelSummary, ThemeSummary
from app.views.errors import ErrorResponse
from app.views.profile import (
    InterestsResponse,
    InterestsUpdateRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
)
from app.views.users import UserResponse

router = APIRouter(prefix="/me", tags=["Perfil"])

_AUTH = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "`UNAUTHENTICATED` ou `TOKEN_INVALID`.",
    }
}


@router.patch(
    "",
    summary="Editar perfil",
    description=(
        "Atualiza `full_name` e `school` (US10). PATCH parcial: campo ausente não "
        "altera; `school` vazia limpa o valor. O e-mail é a identidade da conta "
        "e não pode ser alterado por aqui."
    ),
    response_model=UserResponse,
    responses={
        **_AUTH,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponse,
            "description": "`VALIDATION_ERROR`.",
        },
    },
)
def update_profile(body: ProfileUpdateRequest, user: CurrentUser, db: DbSession) -> UserResponse:
    return UserResponse.model_validate(profile_service.update_profile(db, user, body))


@router.put(
    "/password",
    summary="Trocar senha",
    description=(
        "Troca a senha exigindo a senha atual. `400 CURRENT_PASSWORD_INVALID` se "
        "a senha atual não confere; `422 WEAK_PASSWORD` se a nova não atende às "
        "regras. Em caso de sucesso, **todas as sessões são encerradas** — o "
        "access token atual segue válido até expirar, mas o próximo refresh leva "
        "o app de volta ao login."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **_AUTH,
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "`CURRENT_PASSWORD_INVALID`.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponse,
            "description": "`VALIDATION_ERROR` ou `WEAK_PASSWORD`.",
        },
    },
)
def change_password(body: PasswordChangeRequest, user: CurrentUser, db: DbSession) -> Response:
    profile_service.change_password(db, user, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/interests",
    summary="Definir temas e escolaridades lecionadas",
    description=(
        "Substituição integral dos vínculos do professor (US11): o corpo é o "
        "conjunto completo — `[]` limpa. Esses vínculos alimentam a ordenação "
        "por relevância da busca (`GET /books`). Ids inexistentes respondem "
        "`422` com a lista em `details`."
    ),
    response_model=InterestsResponse,
    responses={
        **_AUTH,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponse,
            "description": "`VALIDATION_ERROR` (ids inexistentes em `details`).",
        },
    },
)
def update_interests(
    body: InterestsUpdateRequest, user: CurrentUser, db: DbSession
) -> InterestsResponse:
    user = profile_service.update_interests(db, user, body.theme_ids, body.education_level_ids)
    themes = sorted(user.themes, key=lambda t: t.name.lower())
    levels = sorted(user.education_levels, key=lambda lv: (lv.sort_order, lv.name.lower()))
    return InterestsResponse(
        themes=[ThemeSummary.model_validate(t) for t in themes],
        education_levels=[EducationLevelSummary.model_validate(lv) for lv in levels],
    )


# --- Minha Seleção (US12) ------------------------------------------------------


@router.get(
    "/saved-books",
    summary="Listar Minha Seleção",
    description=(
        "Obras salvas pelo usuário, da mais recente à mais antiga, no mesmo "
        "formato dos itens de `GET /books`. Lista integral, sem paginação."
    ),
    response_model=list[BookSummary],
    responses=_AUTH,
)
def list_saved_books(user: CurrentUser, db: DbSession) -> list[BookSummary]:
    books = profile_service.list_saved_books(db, user)
    return [BookSummary.from_book(b, is_saved=True) for b in books]


@router.put(
    "/saved-books/{book_id}",
    summary="Salvar obra na seleção",
    description=(
        "Salva a obra na Minha Seleção. Idempotente: salvar uma obra já salva "
        "também responde `204` (seguro repetir após falha de rede)."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **_AUTH,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "`NOT_FOUND`.",
        },
    },
)
def save_book(book_id: int, user: CurrentUser, db: DbSession) -> Response:
    profile_service.save_book(db, user, book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/saved-books/{book_id}",
    summary="Remover obra da seleção",
    description=(
        "Remove a obra da Minha Seleção. Idempotente: remover uma obra que já "
        "não está salva também responde `204`. `404` só quando a obra não existe."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **_AUTH,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "`NOT_FOUND`.",
        },
    },
)
def unsave_book(book_id: int, user: CurrentUser, db: DbSession) -> Response:
    profile_service.unsave_book(db, user, book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
