"""US16: cadastro e renomeação de escolaridades pela editora.

A leitura é aberta a qualquer usuário logado — o professor usa a lista para
filtrar a busca (US08) e para se vincular a escolaridades no perfil (US11).
A ordem da listagem é a pedagógica (`sort_order`: Infantil → Médio).
"""

from fastapi import APIRouter, status

from app.security.dependencies import AdminUser, CurrentUser, DbSession
from app.services import catalog as catalog_service
from app.views.catalog import (
    EducationLevelCreateRequest,
    EducationLevelResponse,
    EducationLevelUpdateRequest,
)
from app.views.errors import ErrorResponse

router = APIRouter(prefix="/education-levels", tags=["Escolaridades"])

_AUTH = {status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}}
_ADMIN_ERRORS = {
    **_AUTH,
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
}


@router.get(
    "",
    summary="Listar escolaridades",
    description=(
        "Escolaridades na ordem pedagógica (`sort_order`), desempatadas pelo nome. "
        "Lista pequena, sem paginação."
    ),
    response_model=list[EducationLevelResponse],
    responses=_AUTH,
)
def list_education_levels(_: CurrentUser, db: DbSession) -> list[EducationLevelResponse]:
    return catalog_service.list_education_levels(db)


@router.post(
    "",
    summary="Criar escolaridade",
    description=(
        "Não é permitido cadastrar duas escolaridades com o mesmo nome, mesmo "
        "mudando a caixa: duplicata responde `409` (`EDUCATION_LEVEL_ALREADY_EXISTS`)."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=EducationLevelResponse,
    responses=_ADMIN_ERRORS,
)
def create_education_level(
    body: EducationLevelCreateRequest, _: AdminUser, db: DbSession
) -> EducationLevelResponse:
    return catalog_service.create_education_level(db, body.name, body.sort_order)


@router.patch(
    "/{level_id}",
    summary="Renomear escolaridade",
    description=(
        'PATCH parcial: campo ausente no corpo significa "não alterar". '
        "Renomear preserva os vínculos com obras e professores (US16)."
    ),
    response_model=EducationLevelResponse,
    responses={
        **_ADMIN_ERRORS,
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def update_education_level(
    level_id: int, body: EducationLevelUpdateRequest, _: AdminUser, db: DbSession
) -> EducationLevelResponse:
    return catalog_service.update_education_level(
        db, level_id, name=body.name, sort_order=body.sort_order
    )
