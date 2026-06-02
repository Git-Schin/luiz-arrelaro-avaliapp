"""Cliente Supabase (Postgres + Storage) compartilhado.

Lê `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` de `st.secrets` (preferencial em
produção/Streamlit Cloud) ou variáveis de ambiente (útil em testes e CLI).
A chave **service_role** é necessária — a anon key não consegue gravar nas
tabelas/buckets sem RLS configurada.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:  # apenas para type-hints — evita import na inicialização
    from supabase import Client

BUCKET_ANEXOS = "avaliapp-anexos"
TABELA_AVALIACOES = "avaliacoes"


class SupaNaoConfigurado(RuntimeError):
    """Levantada quando as credenciais não estão no ambiente.

    A página principal captura e mostra mensagem amigável.
    """


def _get_secret(chave: str) -> str | None:
    # st.secrets só funciona dentro de um run do Streamlit; em scripts auxiliares
    # caímos no fallback de env var sem soltar exceção.
    try:
        val = st.secrets.get(chave)  # type: ignore[attr-defined]
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(chave)


@st.cache_resource(show_spinner=False)
def client() -> "Client":
    """Singleton do cliente Supabase. Cacheado pela vida do processo."""
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SupaNaoConfigurado(
            "Credenciais do Supabase ausentes. Defina SUPABASE_URL e "
            "SUPABASE_SERVICE_KEY em .streamlit/secrets.toml (dev) ou no "
            "dashboard do Streamlit Cloud (produção)."
        )
    from supabase import create_client
    return create_client(url, key)


def configurado() -> bool:
    """Retorna True se as credenciais estão no ambiente."""
    return bool(_get_secret("SUPABASE_URL")) and bool(_get_secret("SUPABASE_SERVICE_KEY"))
