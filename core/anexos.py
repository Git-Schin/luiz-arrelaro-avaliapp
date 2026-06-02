"""
Anexos (fotos) das avaliações — guardados no Supabase Storage.

As fotos NÃO entram no JSON do histórico (evita inchar o banco). Elas vão para
o bucket privado `avaliapp-anexos`, na pasta `aval_<id>/`, e a avaliação guarda
apenas os METADADOS (`nome` + `caminho` = path dentro do bucket). Antes de
salvar (avaliação sem id ainda), as fotos ficam só na sessão como bytes e são
passadas direto ao gerador de PDF.

Schema de metadados (em dados["fotos_imovel"]):
    [{"nome": "frente.jpg", "caminho": "aval_5/frente.jpg"}, ...]
Em memória (sessão / para o PDF):
    [{"nome": "frente.jpg", "bytes": b"..."}]
"""
from __future__ import annotations

import mimetypes
import re

from core.supa import BUCKET_ANEXOS, client

EXTENSOES_OK = {".jpg", ".jpeg", ".png"}


def _slug(nome: str) -> str:
    """Nome de arquivo seguro, preservando a extensão."""
    nome = nome.strip().replace("\\", "/").split("/")[-1]
    base, _, ext = nome.rpartition(".")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base or nome)[:60] or "foto"
    ext = ("." + ext.lower()) if ext else ".jpg"
    if ext not in EXTENSOES_OK:
        ext = ".jpg"
    return f"{base}{ext}"


def _pasta(avaliacao_id: int) -> str:
    return f"aval_{avaliacao_id}"


def _bucket():
    return client().storage.from_(BUCKET_ANEXOS)


def _listar_paths_existentes(avaliacao_id: int) -> list[str]:
    """Devolve os paths atualmente armazenados na pasta da avaliação."""
    try:
        itens = _bucket().list(_pasta(avaliacao_id)) or []
    except Exception:
        return []
    return [f"{_pasta(avaliacao_id)}/{it['name']}" for it in itens if it.get("name")]


def salvar_fotos(avaliacao_id: int, fotos: list[dict]) -> list[dict]:
    """Sobe as fotos (com 'bytes') ao Storage e devolve os metadados.

    Regrava a pasta do zero: apaga o que estava no bucket antes para refletir
    remoções feitas na tela.
    """
    # Apaga arquivos antigos
    paths_velhos = _listar_paths_existentes(avaliacao_id)
    if paths_velhos:
        try:
            _bucket().remove(paths_velhos)
        except Exception:
            pass

    pasta = _pasta(avaliacao_id)
    meta: list[dict] = []
    usados: set[str] = set()
    for f in fotos:
        if not f.get("bytes"):
            continue
        nome = _slug(f.get("nome", "foto.jpg"))
        # Evita colisão de nomes na mesma pasta
        base, _, ext = nome.rpartition(".")
        n, i = nome, 1
        while n in usados:
            n = f"{base}_{i}.{ext}"
            i += 1
        nome = n
        usados.add(nome)

        path = f"{pasta}/{nome}"
        content_type = mimetypes.guess_type(nome)[0] or "image/jpeg"
        _bucket().upload(
            path=path,
            file=f["bytes"],
            file_options={"content-type": content_type, "upsert": "true"},
        )
        meta.append({"nome": nome, "caminho": path})
    return meta


def carregar_fotos(meta: list[dict] | None) -> list[dict]:
    """Metadados (path no bucket) -> lista com 'bytes' (para reabrir/PDF)."""
    fotos: list[dict] = []
    for m in meta or []:
        path = m.get("caminho")
        if not path:
            continue
        try:
            data = _bucket().download(path)
        except Exception:
            continue
        if data:
            fotos.append({"nome": m.get("nome", path.split("/")[-1]), "bytes": data})
    return fotos


def excluir(avaliacao_id: int) -> None:
    """Remove todos os anexos de uma avaliação (ao excluir do histórico)."""
    paths = _listar_paths_existentes(avaliacao_id)
    if paths:
        try:
            _bucket().remove(paths)
        except Exception:
            pass
