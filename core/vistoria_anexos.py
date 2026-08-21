"""Fotos das vistorias — Supabase Storage, bucket `avaliapp-vistorias`."""
from __future__ import annotations

import mimetypes
import re

from core.supa import BUCKET_VISTORIAS, client

EXTENSOES_OK = {".jpg", ".jpeg", ".png"}


def _slug(nome: str) -> str:
    nome = nome.strip().replace("\\", "/").split("/")[-1]
    base, _, ext = nome.rpartition(".")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base or nome)[:60] or "foto"
    ext = ("." + ext.lower()) if ext else ".jpg"
    if ext not in EXTENSOES_OK:
        ext = ".jpg"
    return f"{base}{ext}"


def _pasta(vistoria_id: int) -> str:
    return f"vist_{vistoria_id}"


def _bucket():
    return client().storage.from_(BUCKET_VISTORIAS)


def _listar_paths(vistoria_id: int) -> list[str]:
    try:
        itens = _bucket().list(_pasta(vistoria_id)) or []
    except Exception:
        return []
    return [f"{_pasta(vistoria_id)}/{it['name']}" for it in itens if it.get("name")]


def salvar_fotos_vistoria(vistoria_id: int, comodos: list[dict]) -> list[dict]:
    """Percorre todos os itens de todos os cômodos, sobe fotos com bytes e
    substitui em cada item a lista [{"bytes":...}] por [{"caminho":...}].

    Apaga fotos antigas antes de subir (mesma pasta = nova versão da vistoria).
    Retorna os cômodos com metadados atualizados (sem bytes).
    """
    pasta = _pasta(vistoria_id)

    # Apaga fotos antigas
    paths_velhos = _listar_paths(vistoria_id)
    if paths_velhos:
        try:
            _bucket().remove(paths_velhos)
        except Exception:
            pass

    usados: set[str] = set()

    def _prefix(ci: int, ii: int) -> str:
        return f"c{ci:02d}_i{ii:02d}"

    for ci, comodo in enumerate(comodos):
        for ii, item in enumerate(comodo.get("itens", [])):
            fotos_novas: list[dict] = []
            for f in item.get("fotos", []):
                data = f.get("bytes")
                if not data:
                    # Foto já vinda do storage (tem "caminho") — preserva
                    if f.get("caminho"):
                        fotos_novas.append({"nome": f.get("nome", ""), "caminho": f["caminho"]})
                    continue
                nome = _slug(f.get("nome", "foto.jpg"))
                base, _, ext = nome.rpartition(".")
                n = f"{_prefix(ci, ii)}_{nome}"
                j = 1
                while n in usados:
                    n = f"{_prefix(ci, ii)}_{base}_{j}.{ext}"
                    j += 1
                usados.add(n)
                path = f"{pasta}/{n}"
                content_type = mimetypes.guess_type(n)[0] or "image/jpeg"
                _bucket().upload(
                    path=path,
                    file=data,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
                fotos_novas.append({"nome": n, "caminho": path})
            item["fotos"] = fotos_novas

    return comodos


def carregar_fotos_vistoria(comodos: list[dict]) -> list[dict]:
    """Baixa bytes das fotos que têm "caminho" mas não têm "bytes"."""
    for comodo in comodos:
        for item in comodo.get("itens", []):
            fotos_com_bytes: list[dict] = []
            for f in item.get("fotos", []):
                if f.get("bytes"):
                    fotos_com_bytes.append(f)
                    continue
                caminho = f.get("caminho")
                if not caminho:
                    continue
                try:
                    data = _bucket().download(caminho)
                except Exception:
                    data = None
                if data:
                    fotos_com_bytes.append({"nome": f.get("nome", ""), "bytes": data})
            item["fotos"] = fotos_com_bytes
    return comodos


def excluir(vistoria_id: int) -> None:
    paths = _listar_paths(vistoria_id)
    if paths:
        try:
            _bucket().remove(paths)
        except Exception:
            pass
