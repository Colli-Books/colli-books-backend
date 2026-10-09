# Colli Books Backend

Ambiente Docker com **PostgreSQL** e um **backend FastAPI** (hello world).

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) 24+
- Docker Compose v2 (já incluso no Docker Desktop)

Verifique com:

```bash
docker --version
docker compose version
```

## Estrutura

```
colli-books-backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # aplicação FastAPI
│   ├── database.py       # engine, sessão e Base do SQLAlchemy
│   └── models/           # modelo físico (SQLAlchemy)
│       ├── user.py       # users, invites, password_reset_tokens, refresh_tokens
│       ├── catalog.py    # books, themes, education_levels, institutional_pages
│       └── links.py      # tabelas de associação
├── alembic/
│   ├── env.py
│   └── versions/         # migrations versionadas
├── alembic.ini
├── Dockerfile            # imagem do backend
├── docker-compose.yml    # orquestra db + backend
├── requirements.txt      # dependências Python
└── .env.example          # variáveis de ambiente de exemplo
```

## Como executar

1. Copie o arquivo de variáveis de ambiente:

```bash
cp .env.example .env
```

2. Suba os serviços:

```bash
docker compose up --build
```

Use `-d` para rodar em segundo plano:

```bash
docker compose up --build -d
```

3. Crie as tabelas aplicando as migrations:

```bash
docker compose exec backend alembic upgrade head
```

4. Crie o administrador inicial (idempotente; a senha é pedida no terminal):

```bash
docker compose exec backend python -m app.cli seed-admin --email admin@colli.com --name "Editora Colli"
```

5. Acompanhe os logs (se estiver em segundo plano):

```bash
docker compose logs -f backend
```

## Serviços disponíveis

| Serviço    | URL                        | Credenciais                 |
|------------|----------------------------|-----------------------------|
| Backend    | http://localhost:8000      | —                           |
| Swagger UI | http://localhost:8000/docs | —                           |
| Postgres   | `localhost:5432`           | `postgres` / `postgres`     |

## Documentação da API

A documentação é gerada automaticamente pelo FastAPI a partir do código, seguindo o
padrão [OpenAPI 3.1](https://www.openapis.org/). Não é preciso escrever nem manter
nada à mão: ao adicionar um endpoint, ele aparece na página sozinho.

Com os containers no ar, acesse **http://localhost:8000/docs** (Swagger UI). A página
lista todos os endpoints agrupados por tag e permite **executar** as requisições direto
do navegador, pelo botão *Try it out*.

### Endpoints

| Método | Rota      | Tag    | Descrição                                  | Respostas  |
|--------|-----------|--------|--------------------------------------------|------------|
| `GET`  | `/`       | Root   | Hello world; confirma que a API está no ar | `200`      |
| `GET`  | `/health` | Health | Executa `SELECT 1` no PostgreSQL           | `200`, `503` |
| `POST` | `/api/v1/auth/login` | Auth | Login com e-mail e senha (US03) | `200`, `401`, `429` |
| `POST` | `/api/v1/auth/refresh` | Auth | Troca o refresh token por um par novo (rotação) | `200`, `401` |
| `POST` | `/api/v1/auth/logout` | Auth | Revoga o refresh token | `204` |
| `GET`  | `/api/v1/auth/me` | Auth | Dados e papel do usuário logado (US05) | `200`, `401` |
| `POST` | `/api/v1/invites/verify` | Convites | Confere o convite e devolve o e-mail (US02) | `200`, `404`, `409`, `410` |
| `POST` | `/api/v1/invites/accept` | Convites | Define a senha, ativa a conta e autentica (US02) | `200`, `404`, `409`, `410`, `422` |
| `POST` | `/api/v1/invites/resend` | Convites | Reenvia convite expirado por e-mail (US02) | `202` |
| `POST` | `/api/v1/admin/teachers` | Admin | Cadastra professor e devolve o link de convite (US01) | `201`, `401`, `403`, `409` |
| `POST` | `/api/v1/admin/teachers/{id}/invite` | Admin | Gera novo convite e invalida o anterior | `200`, `401`, `403`, `404`, `409` |

### Testando o backend

```bash
curl http://localhost:8000
# {"message":"Hello World"}

curl http://localhost:8000/health
# {"status":"ok","database":"connected"}

# com o banco fora do ar, o mesmo endpoint responde 503:
docker compose stop db
curl -i http://localhost:8000/health
# HTTP/1.1 503 Service Unavailable
# {"status":"error","database":"(psycopg.OperationalError) ..."}
docker compose start db
```

### Documentando novos endpoints

Os metadados da página ficam em `app/main.py`:

- `FastAPI(title=..., description=..., version=..., openapi_tags=...)` controla o
  cabeçalho da página e a descrição de cada tag.
- Em cada rota, `tags`, `summary`, `description` e `response_model` definem como o
  endpoint aparece na documentação.
- Os modelos Pydantic (`HelloResponse`, `HealthResponse`) viram os *schemas* exibidos
  no rodapé da página, com os exemplos definidos em `Field(..., examples=[...])`.

## Testes automatizados

Os testes de integração rodam contra um **PostgreSQL real** (o schema usa `unaccent`,
`pg_trgm` e índices GIN, que não existem no SQLite). O `conftest.py` recria o banco
`colli_books_test` do zero, aplica as migrations e desfaz cada teste com rollback.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d db
pytest
```

Para usar outro servidor, defina `TEST_DATABASE_URL` (o nome do banco precisa
terminar em `_test`). As dependências de desenvolvimento ficam em
`requirements-dev.txt`, para não irem para a imagem Docker.

## Banco de dados

O modelo físico é definido em `app/models/` (SQLAlchemy 2.0) e materializado no
PostgreSQL pelas migrations do **Alembic**, em `alembic/versions/`. Os models são a
fonte de verdade: nenhuma tabela é criada à mão no banco.

### Tabelas

| Tabela | Para que serve | Estórias |
|---|---|---|
| `users` | Contas de professor e administrador, diferenciadas por `role` | US01, US03, US05, US10 |
| `invites` | Tokens de convite de primeiro acesso (uso único) | US01, US02 |
| `password_reset_tokens` | Tokens de "Esqueci minha senha" (uso único) | US04, US06 |
| `refresh_tokens` | Refresh tokens revogáveis, para o logout encerrar a sessão | US03 |
| `books` | Obras do acervo | US09, US15 |
| `themes` | Temas cadastrados pela editora | US16 |
| `education_levels` | Escolaridades cadastradas pela editora | US16 |
| `book_themes` | Vínculo obra ↔ temas (N:N) | US17 |
| `teacher_themes` | Temas que o professor leciona (N:N) | US11 |
| `teacher_education_levels` | Escolaridades que o professor atende (N:N) | US11 |
| `saved_books` | "Minha Seleção" do professor (N:N) | US12 |
| `institutional_pages` | Seções institucionais do menu lateral | US18 |

### Regras garantidas pelo próprio banco

Algumas regras do backlog são invariantes de dado, não de aplicação, e por isso valem
como constraint — um bug na API não consegue furá-las:

| Constraint | Regra |
|---|---|
| `ck_users_active_requires_password` | Conta `active` sem hash de senha não existe (US01: enquanto a senha não for definida, o login é bloqueado). |
| `ck_users_email_lowercase` | E-mail sempre normalizado em minúsculas, o que torna a UNIQUE insensível a caixa. |
| `uq_themes_name_lower` / `uq_education_levels_name_lower` | Nomes duplicados ignorando maiúsculas/minúsculas são rejeitados (US16). |
| `fk_books_education_level_id...ON DELETE SET NULL` | Apagar uma escolaridade não apaga obras; a obra permanece no acervo sem escolaridade (US17). |
| `ck_institutional_pages_has_content` | Uma seção institucional tem conteúdo próprio ou aponta para uma URL externa — nunca nenhum dos dois (US18). |

### Busca sem acento (US07)

A US07 exige busca por título ignorando acentuação e caixa. `unaccent` não é `IMMUTABLE`
e por isso não pode ser indexada diretamente; a migration inicial cria o wrapper
`immutable_unaccent(text)` e índices GIN/trigram sobre `immutable_unaccent(lower(title))`
e `immutable_unaccent(lower(author))`. A consulta correspondente é:

```sql
SELECT * FROM books
WHERE immutable_unaccent(lower(title)) LIKE '%' || immutable_unaccent(lower(:termo)) || '%';
```

### Migrations

```bash
# aplicar todas as migrations pendentes
docker compose exec backend alembic upgrade head

# gerar uma nova migration a partir das mudanças nos models
docker compose exec backend alembic revision --autogenerate -m "descricao da mudanca"

# conferir se os models e o banco estão sincronizados
docker compose exec backend alembic check

# ver a revisão aplicada no banco
docker compose exec backend alembic current

# desfazer a última migration
docker compose exec backend alembic downgrade -1
```

> **Atenção:** sempre revise o arquivo gerado pelo `--autogenerate` antes de aplicar. O
> Alembic não detecta renomeações (vê como *drop* + *create*, o que apaga dados) e não
> compara índices funcionais que usam classe de operador.


## Comandos úteis

```bash
# parar os containers (mantém os dados)
docker compose down

# parar e apagar os volumes (apaga o banco)
docker compose down -v

# reconstruir apenas o backend
docker compose up --build backend

# abrir um shell no container do backend
docker compose exec backend bash

# abrir o psql no container do banco
docker compose exec db psql -U postgres -d colli_books

# ver o status dos serviços
docker compose ps
```
