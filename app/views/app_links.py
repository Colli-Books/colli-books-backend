"""Página HTML que faz a ponte entre o link https do e-mail e o app.

Clientes de e-mail e o WhatsApp não deixam clicável um link `collibooks://`. Por
isso o e-mail leva um link https para esta página, que oferece o botão "Abrir no
app" (com o esquema customizado) e, no convite, o código para colar na tela
"Tenho um convite".
"""

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class OpenPageCopy:
    title: str
    lead: str
    show_code: bool


PAGE_COPY: dict[str, OpenPageCopy] = {
    "convite": OpenPageCopy(
        title="Seu convite para o Colli Books",
        lead="Toque no botão para abrir o app e concluir seu cadastro.",
        show_code=True,
    ),
    "redefinir-senha": OpenPageCopy(
        title="Redefinir sua senha",
        lead="Toque no botão para abrir o app e criar uma nova senha.",
        show_code=False,
    ),
}

_STYLE = """
:root { color-scheme: light dark; --fg: #1d1d1f; --muted: #5f6368; --bg: #f5f5f7;
  --card: #fff; --accent: #c0392b; --border: #e0e0e0; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #f5f5f7; --muted: #a1a1a6; --bg: #121212; --card: #1e1e1e; --border: #333; }
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 16px; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { width: 100%; max-width: 420px; background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; padding: 28px 24px; text-align: center; }
h1 { font-size: 1.35rem; margin: 0 0 8px; }
p { color: var(--muted); line-height: 1.5; margin: 0 0 20px; }
.btn { display: block; width: 100%; padding: 14px; border-radius: 10px; border: 0;
  font-size: 1rem; font-weight: 600; text-decoration: none; cursor: pointer; }
.primary { background: var(--accent); color: #fff; }
.secondary { background: transparent; color: var(--fg); border: 1px solid var(--border);
  margin-top: 10px; }
.code { margin: 24px 0 0; padding-top: 20px; border-top: 1px solid var(--border); }
.code p { margin-bottom: 10px; }
code { display: block; word-break: break-all; padding: 12px; border-radius: 8px;
  background: var(--bg); font-size: .9rem; user-select: all; }
.error h1 { color: var(--accent); }
"""

_COPY_SCRIPT = """
document.getElementById("copy").addEventListener("click", async (ev) => {
  const code = document.getElementById("code").textContent;
  try { await navigator.clipboard.writeText(code); ev.target.textContent = "Código copiado"; }
  catch { ev.target.textContent = "Selecione o código e copie"; }
});
"""


def _document(body: str, nonce: str, *, with_script: bool) -> str:
    script = f'<script nonce="{escape(nonce)}">{_COPY_SCRIPT}</script>' if with_script else ""
    return (
        "<!doctype html>"
        '<html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex">'
        "<title>Colli Books</title>"
        f'<style nonce="{escape(nonce)}">{_STYLE}</style>'
        f"</head><body>{body}{script}</body></html>"
    )


def render_open_page(copy: OpenPageCopy, app_link: str, token: str, nonce: str) -> str:
    code_block = ""
    if copy.show_code:
        code_block = (
            '<div class="code">'
            "<p>O app não abriu? Abra o Colli Books, toque em "
            "<strong>Tenho um convite</strong> e cole este código:</p>"
            f'<code id="code">{escape(token)}</code>'
            '<button type="button" id="copy" class="btn secondary">Copiar código</button>'
            "</div>"
        )
    body = (
        "<main>"
        f"<h1>{escape(copy.title)}</h1>"
        f"<p>{escape(copy.lead)}</p>"
        f'<a class="btn primary" href="{escape(app_link)}">Abrir no app</a>'
        f"{code_block}"
        "</main>"
    )
    return _document(body, nonce, with_script=copy.show_code)


def render_invalid_link_page(nonce: str) -> str:
    body = (
        '<main class="error">'
        "<h1>Link inválido</h1>"
        "<p>Este link está incompleto ou foi alterado. Abra de novo o link do e-mail "
        "ou peça um novo à editora.</p>"
        "</main>"
    )
    return _document(body, nonce, with_script=False)
