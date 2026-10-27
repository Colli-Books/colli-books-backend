"""Views das obras (US07–US09, US15, US17).

`BookSummary` é o cartão do catálogo e `BookDetail`, a tela de detalhe; os
models `*Form` são a entrada `multipart/form-data` de `POST/PATCH /books`.

Convenção do PATCH multipart (form não tem `null`):

* campo ausente → não alterar;
* campo texto/numérico enviado vazio (`""`) → limpar (vira `NULL`);
* `theme_ids` só com vazio (`theme_ids=`) → remover todos os temas.

`model_fields_set` registra o que foi enviado; o service decide o que mudar.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import UploadFile
from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.views.catalog import EducationLevelSummary, ThemeSummary

if TYPE_CHECKING:
    from app.models import Book

BookSort = Literal["relevance", "title", "year"]

_Required = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
_OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]

_URL_SCHEMES = ("http://", "https://")


def _blank_to_none(value: object) -> object:
    """Em multipart, campo opcional enviado vazio significa "sem valor"."""
    if value == "":
        return None
    return value


def _validate_url(value: str | None) -> str | None:
    """Links externos precisam ser http(s) — o app os abre fora do aplicativo."""
    if value is not None and not value.startswith(_URL_SCHEMES):
        raise ValueError("URL inválida: precisa começar com http:// ou https://")
    return value


def _strip_empty_ids(values: object) -> object:
    """`theme_ids=` (vazio) vira `[]`: PATCH lê isso como "remover todos"."""
    if not isinstance(values, list):
        return values
    return [v for v in values if v != ""]


# --- Saída ------------------------------------------------------------------


class BookSummary(BaseModel):
    """Obra no formato do cartão do catálogo — também é o item da Minha Seleção."""

    id: int = Field(..., examples=[7])
    title: str = Field(..., examples=["O Segredo de Aurora"])
    author: str = Field(..., examples=["Andréa Avelar"])
    cover_url: str | None = Field(None, examples=["/media/covers/3fa9f1.png"])
    year: int | None = Field(None, examples=[2026])
    education_level: EducationLevelSummary | None = None
    themes: list[ThemeSummary]
    # Estado da "Minha Seleção" do usuário logado — elimina a consulta por obra.
    is_saved: bool = False

    @classmethod
    def from_book(cls, book: "Book", is_saved: bool) -> "BookSummary":
        themes = sorted(book.themes, key=lambda t: t.name.lower())
        return cls(
            id=book.id,
            title=book.title,
            author=book.author,
            cover_url=book.cover_url,
            year=book.year,
            education_level=(
                EducationLevelSummary.model_validate(book.education_level)
                if book.education_level is not None
                else None
            ),
            themes=[ThemeSummary.model_validate(t) for t in themes],
            is_saved=is_saved,
        )


class BookDetail(BookSummary):
    """Obra completa — resposta do detalhe (US09) e do cadastro/edição (US15)."""

    synopsis: str | None = Field(None, examples=["Aurora ama dançar balé..."])
    isbn: str | None = Field(None, examples=["978-65-6079-046-9"])
    page_count: int | None = Field(None, examples=[38])
    edition: str | None = Field(None, examples=["1ª"])
    store_url: str | None = Field(
        None, examples=["https://www.collibooksloja.com/infantil/o-segredo-de-aurora"]
    )
    book_url: str | None = Field(
        None, examples=["https://www.collibooks.com/o-segredo-de-aurora-lp/"]
    )
    pedagogical_material_url: str | None = Field(
        None, examples=["https://www.collibooks.com/wp-content/uploads/ficha.pdf"]
    )
    created_at: datetime = Field(..., examples=["2026-10-20T09:30:00Z"])
    updated_at: datetime = Field(..., examples=["2026-10-25T14:15:00Z"])

    @classmethod
    def from_book(cls, book: "Book", is_saved: bool) -> "BookDetail":
        summary = BookSummary.from_book(book, is_saved)
        return cls(
            **summary.model_dump(),
            synopsis=book.synopsis,
            isbn=book.isbn,
            page_count=book.page_count,
            edition=book.edition,
            store_url=book.store_url,
            book_url=book.book_url,
            pedagogical_material_url=book.pedagogical_material_url,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )


# --- Entrada (multipart/form-data) -------------------------------------------


class _BookFormBase(BaseModel):
    """Campos e validadores comuns ao cadastro e à edição.

    Campos numéricos aceitam `""` como "sem valor" porque todo campo multipart
    chega como texto.
    """

    synopsis: str | None = None
    isbn: _OptionalText | None = Field(None, max_length=20)
    page_count: int | None = Field(None, gt=0, examples=[38])
    edition: _OptionalText | None = Field(None, max_length=50, examples=["1ª"])
    year: int | None = Field(None, ge=1000, le=9999, examples=[2026])
    store_url: str | None = None
    book_url: str | None = None
    pedagogical_material_url: str | None = None
    education_level_id: int | None = None
    cover: UploadFile | None = None

    @field_validator(
        "synopsis",
        "edition",
        "store_url",
        "book_url",
        "pedagogical_material_url",
        "page_count",
        "year",
        "education_level_id",
        "isbn",
        mode="before",
    )
    @classmethod
    def _empty_means_absent(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("store_url", "book_url", "pedagogical_material_url")
    @classmethod
    def _urls_are_http(cls, value: str | None) -> str | None:
        return _validate_url(value)


class BookCreateForm(_BookFormBase):
    """Form de `POST /books` (US15/17). Título e autor são obrigatórios."""

    title: _Required = Field(..., examples=["O Segredo de Aurora"])
    author: _Required = Field(..., examples=["Andréa Avelar"])
    theme_ids: list[int] = Field(default_factory=list, examples=[6, 8])

    _strip_theme_ids = field_validator("theme_ids", mode="before")(_strip_empty_ids)


class BookUpdateForm(_BookFormBase):
    """Form de `PATCH /books/{id}`. Tudo opcional; ver convenção no topo do módulo."""

    title: _Required | None = None
    author: _Required | None = None
    theme_ids: list[int] | None = None

    _strip_theme_ids = field_validator("theme_ids", mode="before")(_strip_empty_ids)
