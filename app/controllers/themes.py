"""US16: cadastro e renomeação de temas pela editora.

A leitura é aberta a qualquer usuário logado — o professor usa a lista para
filtrar a busca (US08) e para se vincular a temas no perfil (US11).
"""

from fastapi import APIRouter, status

from app.security.dependencies import AdminUser, CurrentUser, DbSession
from app.services import catalog as catalog_service
from app.views.catalog import ThemeCreateRequest, ThemeResponse, ThemeUpdateRequest
from app.views.errors import ErrorResponse

router = APIRouter(prefix="/themes", tags=["Temas"])

_AUTH = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "`UNAUTHENTICATED` ou `TOKEN_INVALID`.",
    }
}
_ADMIN_ERRORS = {
    **_AUTH,
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "`FORBIDDEN` (exige papel `admin`).",
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "`THEME_ALREADY_EXISTS`.",
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "`VALIDATION_ERROR`.",
    },
}


@router.get(
    "",
    summary="Listar temas",
    description="Temas disponíveis, em ordem alfabética. Lista pequena, sem paginação.",
    response_model=list[ThemeResponse],
    responses=_AUTH,
)
def list_themes(_: CurrentUser, db: DbSession) -> list[ThemeResponse]:
    return catalog_service.list_themes(db)


@router.post(
    "",
    summary="Criar tema",
    description=(
        "Não é permitido cadastrar dois temas com o mesmo nome, mesmo mudando a "
        "caixa: duplicata responde `409` (`THEME_ALREADY_EXISTS`)."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=ThemeResponse,
    responses=_ADMIN_ERRORS,
)
def create_theme(body: ThemeCreateRequest, _: AdminUser, db: DbSession) -> ThemeResponse:
    return catalog_service.create_theme(db, body.name, body.description)


@router.patch(
    "/{theme_id}",
    summary="Renomear tema",
    description=(
        'PATCH parcial: campo ausente no corpo significa "não alterar". '
        "Renomear preserva os vínculos com as obras (US16)."
    ),
    response_model=ThemeResponse,
    responses={
        **_ADMIN_ERRORS,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "`NOT_FOUND`.",
        },
    },
)
def update_theme(
    theme_id: int, body: ThemeUpdateRequest, _: AdminUser, db: DbSession
) -> ThemeResponse:
    return catalog_service.update_theme(db, theme_id, name=body.name, description=body.description)
