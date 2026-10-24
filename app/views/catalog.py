"""Views dos temas e escolaridades (US16): listagens e cadastro/renomeação."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.views.common import blank_to_none

_Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ThemeSummary(BaseModel):
    """Tema no formato mínimo, reutilizado nas respostas de obras e perfil."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., examples=[6])
    name: str = Field(..., examples=["Inclusão"])


class ThemeResponse(ThemeSummary):
    description: str | None = Field(None, examples=["Obras sobre inclusão e acessibilidade"])


class ThemeCreateRequest(BaseModel):
    name: _Name = Field(..., examples=["Empatia"])
    description: str | None = Field(None, examples=["Obras que trabalham empatia e respeito"])

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return blank_to_none(value)


class ThemeUpdateRequest(BaseModel):
    """PATCH parcial: campo ausente ou vazio = não alterar (não há "limpar" campo a campo)."""

    name: _Name | None = Field(None, examples=["Empatia"])
    description: str | None = Field(None, examples=["Obras que trabalham empatia"])

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return blank_to_none(value)


class EducationLevelSummary(BaseModel):
    """Escolaridade no formato mínimo, reutilizada nas respostas de obras e perfil."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["Educação Infantil"])


class EducationLevelResponse(EducationLevelSummary):
    """Escolaridade na listagem/edição — `sort_order` expõe a ordem pedagógica."""

    sort_order: int = Field(..., examples=[1])


class EducationLevelCreateRequest(BaseModel):
    name: _Name = Field(..., examples=["Ensino Médio"])
    sort_order: int = Field(
        0, description="Ordem pedagógica na exibição (Infantil → Médio).", examples=[4]
    )


class EducationLevelUpdateRequest(BaseModel):
    name: _Name | None = Field(None, examples=["Ensino Médio"])
    sort_order: int | None = Field(None, examples=[4])
