"""Armazenamento das capas enviadas pelo admin (US15).

Os arquivos ficam em `<media_dir>/covers/`, servidos pelo mount `/media` de
`app/main.py`; o `cover_url` gravado é o caminho relativo. A validação confere
o Content-Type *e* os bytes mágicos — o cabeçalho é definido pelo cliente.
"""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, status

from app.config import get_settings
from app.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

# Content-Type aceito → extensão gravada. A assinatura é conferida nos bytes.
_MIME_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_READ_CHUNK = 64 * 1024

_COVERS_SUBDIR = "covers"


def _image_invalid() -> AppError:
    return AppError(
        ErrorCode.IMAGE_INVALID,
        "A capa precisa ser um arquivo PNG ou JPEG.",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def save_cover(upload: UploadFile) -> str:
    """Valida e grava a capa enviada. Retorna o `cover_url` público (relativo).

    Levanta `IMAGE_INVALID` (tipo errado) ou `IMAGE_TOO_LARGE` (acima de
    `cover_max_bytes`). Não faz nada no banco — quem chama decide o commit.
    """
    extension = _MIME_EXTENSIONS.get(upload.content_type or "")
    if extension is None:
        raise _image_invalid()

    settings = get_settings()
    covers_dir = Path(settings.media_dir) / _COVERS_SUBDIR
    covers_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    path = covers_dir / filename

    size = _write_bounded(upload, path, settings.cover_max_bytes)
    if size == 0:
        path.unlink(missing_ok=True)
        raise _image_invalid()
    return f"/media/{_COVERS_SUBDIR}/{filename}"


def _write_bounded(upload: UploadFile, path: Path, max_bytes: int) -> int:
    """Grava com limite de tamanho, conferindo a assinatura PNG/JPEG no 1º chunk."""
    written = 0
    try:
        with path.open("wb") as out:
            while chunk := upload.file.read(_READ_CHUNK):
                written += len(chunk)
                if written == len(chunk) and not (
                    chunk.startswith(_PNG_SIGNATURE) or chunk.startswith(_JPEG_SIGNATURE)
                ):
                    raise _image_invalid()
                if written > max_bytes:
                    raise AppError(
                        ErrorCode.IMAGE_TOO_LARGE,
                        f"A capa pode ter no máximo {max_bytes // (1024 * 1024)} MB.",
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
                out.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return written


def delete_cover(cover_url: str | None) -> None:
    """Remove o arquivo de uma `cover_url` gerada por `save_cover`.

    Best-effort: falha ao apagar não pode derrubar a requisição que atualizou a
    obra — no pior caso sobra um arquivo órfão na pasta.
    """
    prefix = f"/media/{_COVERS_SUBDIR}/"
    if not cover_url or not cover_url.startswith(prefix):
        return
    name = Path(cover_url).name  # descarta qualquer diretório do caminho
    try:
        (Path(get_settings().media_dir) / _COVERS_SUBDIR / name).unlink(missing_ok=True)
    except OSError:
        logger.warning("Não foi possível apagar a capa %s", cover_url)
