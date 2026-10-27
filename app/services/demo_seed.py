"""Seed de demonstração (`python -m app.cli seed-demo`).

Popula temas, escolaridades e obras com os dados do protótipo do app
(`catalogo_data.dart`), e as páginas institucionais com URLs de base — a tabela
existe, mas não há API de leitura no MVP (o app abre os links do site direto).

Idempotente: a deduplicação é por nome ignorando caixa (temas/escolaridades),
ISBN (obras) e slug (páginas institucionais).
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, EducationLevel, InstitutionalPage, Theme

EDUCATION_LEVELS = [
    "Educação Infantil",
    "Ensino Fundamental I",
    "Ensino Fundamental II",
    "Ensino Médio",
]

THEMES = [
    "Bullying",
    "Imaginação",
    "Higiene",
    "Alimentação",
    "Aventura",
    "Mistério",
    "Inclusão",
    "Diversidade",
    "Representatividade",
    "Empatia",
    "Amizade",
    "Arte e Expressão Corporal",
    "Autoestima",
    "Cooperação",
]

# URLs de base do site da editora — referência editável direto no banco.
INSTITUTIONAL_PAGES = [
    ("home", "Home", "https://www.collibooks.com/"),
    ("editora", "Editora", "https://www.collibooks.com/editora/"),
    ("pnld", "PNLD", "https://www.collibooks.com/pnld-2/"),
    ("catalogo", "Catálogo", "https://www.collibooks.com/"),
    ("blog", "Blog", "https://www.collibooks.com/category/blog/"),
    ("anima-kids", "Anima Kids", "https://www.collibooks.com/anima-kids/"),
    ("contato", "Contato", "https://www.collibooks.com/"),
]

# Mesma lista do mock do app. Uma obra tem UMA escolaridade (US17): quando o
# mock lista mais de uma, fica a primeira. `cover_url` usa as URLs públicas do
# mock; quem tinha imagem local no app fica sem capa aqui.
BOOKS: list[dict] = [
    {
        "title": "O Segredo de Aurora",
        "author": "Andréa Avelar",
        "synopsis": (
            "Aurora ama dançar balé. Quando suas sapatilhas tocam o chão, tudo parece "
            "entrar no ritmo da alegria. Mas um segredo guardado quase tira dela a "
            "chance de subir ao palco. Com emoção e delicadeza, O Segredo de Aurora "
            "mostra que a arte existe para acolher, unir pessoas e fazer cada criança "
            "acreditar que também pode brilhar."
        ),
        "isbn": "978-65-6079-046-9",
        "page_count": 38,
        "edition": "1ª",
        "year": 2026,
        "cover_url": None,
        "store_url": "https://www.collibooksloja.com/infantil/o-segredo-de-aurora",
        "book_url": "https://www.collibooks.com/o-segredo-de-aurora-lp/",
        "pedagogical_material_url": (
            "https://www.collibooks.com/wp-content/uploads/2026/07/FICHA_O-SEGREDO-DE-AURORA.pdf"
        ),
        "education_level": "Educação Infantil",
        "themes": [
            "Diversidade",
            "Inclusão",
            "Representatividade",
            "Empatia",
            "Amizade",
            "Arte e Expressão Corporal",
            "Autoestima",
            "Cooperação",
        ],
    },
    {
        "title": "O Mistério da Floresta",
        "author": "Isa Colli",
        "synopsis": (
            "Uma aventura mágica que leva os pequenos leitores ao coração de uma "
            "floresta encantada. Quando dois amigos, Pedro e Sofia, descobrem um mapa "
            "antigo escondido no sótão de seus avós, eles embarcam em uma jornada para "
            "desvendar um segredo guardado há gerações pelas criaturas da mata."
        ),
        "isbn": "978-85-12345-67-8",
        "page_count": 48,
        "edition": "1ª",
        "year": 2023,
        "cover_url": "https://images.unsplash.com/photo-1516979187457-637abb4f9353?w=400&q=80",
        "store_url": "https://www.collibooksloja.com/",
        "book_url": "https://www.collibooks.com/editora/",
        "pedagogical_material_url": "https://www.collibooks.com/pnld-2/",
        "education_level": "Ensino Fundamental I",
        "themes": ["Aventura", "Mistério"],
    },
    {
        "title": "Aventuras na Matemática Vol. 1",
        "author": "Maria Silva, João Santos",
        "synopsis": (
            "Uma jornada divertida pelo mundo dos números, estimulando o raciocínio "
            "lógico e a cooperação entre os alunos em sala de aula."
        ),
        "isbn": "978-85-209-1234-1",
        "page_count": 84,
        "edition": "2ª",
        "year": 2023,
        "cover_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400&q=80",
        "store_url": "https://www.collibooksloja.com/",
        "book_url": "https://www.collibooks.com/editora/",
        "pedagogical_material_url": "https://www.collibooks.com/pnld-2/",
        "education_level": "Ensino Fundamental I",
        "themes": ["Bullying", "Imaginação"],
    },
    {
        "title": "Caminhos da Leitura",
        "author": "Ana Oliveira",
        "synopsis": (
            "Contos e atividades pedagógicas dinâmicas para despertar o amor pela "
            "leitura e interpretação de texto."
        ),
        "isbn": "978-85-209-5678-2",
        "page_count": 96,
        "edition": "1ª",
        "year": 2022,
        "cover_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=400&q=80",
        "store_url": "https://www.collibooksloja.com/",
        "book_url": "https://www.collibooks.com/editora/",
        "pedagogical_material_url": "https://www.collibooks.com/pnld-2/",
        "education_level": "Ensino Fundamental I",
        "themes": ["Imaginação", "Bullying"],
    },
    {
        "title": "Ciências: Descobertas e Aventuras",
        "author": "Carlos Drummond",
        "synopsis": (
            "Explorações sobre o corpo humano, hábitos saudáveis e os mistérios da "
            "natureza para crianças curiosas."
        ),
        "isbn": "978-85-209-9012-3",
        "page_count": 112,
        "edition": "1ª",
        "year": 2024,
        "cover_url": "https://images.unsplash.com/photo-1532012164546-f432f2e3777f?w=400&q=80",
        "store_url": "https://www.collibooksloja.com/",
        "book_url": "https://www.collibooks.com/editora/",
        "pedagogical_material_url": "https://www.collibooks.com/pnld-2/",
        "education_level": "Ensino Fundamental I",
        "themes": ["Higiene", "Alimentação"],
    },
    {
        "title": "Histórias de Ninar e Imaginação",
        "author": "Clarice Lispector",
        "synopsis": (
            "Narrativas poéticas para desenvolver a sensibilidade e imaginação na "
            "primeira infância."
        ),
        "isbn": "978-85-209-3456-7",
        "page_count": 64,
        "edition": "1ª",
        "year": 2021,
        "cover_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=400&q=80",
        "store_url": "https://www.collibooksloja.com/",
        "book_url": "https://www.collibooks.com/editora/",
        "pedagogical_material_url": "https://www.collibooks.com/pnld-2/",
        "education_level": "Educação Infantil",
        "themes": ["Imaginação", "Inclusão"],
    },
    {
        "title": "O Pequeno Príncipe",
        "author": "Antoine de Saint-Exupéry",
        "synopsis": (
            "Uma fábula sobre a amizade, a empatia e o verdadeiro sentido das coisas "
            "que são invisíveis aos olhos."
        ),
        "isbn": "978-85-209-7890-4",
        "page_count": 128,
        "edition": "3ª",
        "year": 2020,
        "cover_url": "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=400&q=80",
        "store_url": "https://www.collibooksloja.com/",
        "book_url": "https://www.collibooks.com/editora/",
        "pedagogical_material_url": "https://www.collibooks.com/pnld-2/",
        "education_level": "Ensino Fundamental II",
        "themes": ["Aventura", "Inclusão"],
    },
]


@dataclass(frozen=True)
class SeedReport:
    themes_created: int
    education_levels_created: int
    books_created: int
    institutional_pages_created: int


def _get_or_create_by_name(db: Session, model, name: str, **defaults):
    existing = db.scalar(select(model).where(func.lower(model.name) == name.lower()))
    if existing is not None:
        return existing, False
    row = model(name=name, **defaults)
    db.add(row)
    db.flush()
    return row, True


def seed_demo(db: Session) -> SeedReport:
    """Insere os dados de demonstração. Idempotente. Faz commit."""
    themes_created = 0
    levels_created = 0
    pages_created = 0
    books_created = 0

    themes: dict[str, Theme] = {}
    for name in THEMES:
        theme, created = _get_or_create_by_name(db, Theme, name)
        themes[name] = theme
        themes_created += created

    levels: dict[str, EducationLevel] = {}
    for order, name in enumerate(EDUCATION_LEVELS, start=1):
        level, created = _get_or_create_by_name(db, EducationLevel, name, sort_order=order)
        levels[name] = level
        levels_created += created

    for order, (slug, title, url) in enumerate(INSTITUTIONAL_PAGES, start=1):
        if db.scalar(select(InstitutionalPage).where(InstitutionalPage.slug == slug)):
            continue
        db.add(InstitutionalPage(slug=slug, title=title, external_url=url, sort_order=order))
        pages_created += 1
    db.flush()

    for data in BOOKS:
        if db.scalar(select(Book.id).where(Book.isbn == data["isbn"])) is not None:
            continue
        book = Book(
            title=data["title"],
            author=data["author"],
            synopsis=data["synopsis"],
            isbn=data["isbn"],
            page_count=data["page_count"],
            edition=data["edition"],
            year=data["year"],
            cover_url=data["cover_url"],
            store_url=data["store_url"],
            book_url=data["book_url"],
            pedagogical_material_url=data["pedagogical_material_url"],
            education_level=levels.get(data["education_level"]),
        )
        book.themes = [themes[name] for name in data["themes"] if name in themes]
        db.add(book)
        books_created += 1

    db.commit()
    return SeedReport(themes_created, levels_created, books_created, pages_created)
