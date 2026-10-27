"""Views do perfil do usuário logado (US10–US12): `/me`.

O usuário é sempre o dono do access token — nenhum endpoint aqui recebe id de
usuário (correção sobre o desenho original, seção 9 do contrato).
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.views.catalog import EducationLevelSummary, ThemeSummary
from app.views.common import blank_to_none


class ProfileUpdateRequest(BaseModel):
    """PATCH parcial: campo ausente = não alterar; `school` vazia vira `null`.

    O e-mail não aparece aqui de propósito: é a identidade da conta (US10 o
    marca como somente leitura).
    """

    full_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
        | None
    ) = Field(None, examples=["Maria Souza"])
    school: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = Field(
        None, examples=["E.E. Machado de Assis"]
    )

    @field_validator("school")
    @classmethod
    def _blank_school_is_none(cls, value: str | None) -> str | None:
        return blank_to_none(value)


class PasswordChangeRequest(BaseModel):
    """Troca de senha autenticada: exige a senha atual para que um aparelho
    desatento não sirva para trocar a senha."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., examples=["nova-senha-segura"])


class InterestsUpdateRequest(BaseModel):
    """Temas e escolaridades que o professor leciona (US11).

    Substituição integral e idempotente: o que está no corpo passa a ser o
    conjunto completo — `[]` limpa os vínculos daquele tipo.
    """

    theme_ids: list[int] = Field(default_factory=list, examples=[[6, 8]])
    education_level_ids: list[int] = Field(default_factory=list, examples=[[2]])


class InterestsResponse(BaseModel):
    themes: list[ThemeSummary]
    education_levels: list[EducationLevelSummary]
