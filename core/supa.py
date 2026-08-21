"""Cliente Supabase (Postgres + Storage) compartilhado.

Lê `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` de `st.secrets` (produção/Streamlit
Cloud) ou variáveis de ambiente (testes/CLI).

A chave **service_role** é usada para operações de dados (bypassa RLS).
Para autenticação de usuários (sign_in, sign_up), usa-se `auth_client()` com
a chave anon (`SUPABASE_ANON_KEY`) ou service_role como fallback.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from supabase import Client

BUCKET_ANEXOS = "avaliapp-anexos"
BUCKET_VISTORIAS = "avaliapp-vistorias"
TABELA_AVALIACOES = "avaliacoes"
TABELA_PERFIS = "perfis"
TABELA_VISTORIAS = "vistorias"


class SupaNaoConfigurado(RuntimeError):
    """Levantada quando as credenciais não estão no ambiente."""


def _get_secret(chave: str) -> str | None:
    try:
        val = st.secrets.get(chave)  # type: ignore[attr-defined]
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(chave)


@st.cache_resource(show_spinner=False)
def client() -> "Client":
    """Singleton do cliente Supabase com service_role. Cacheado pelo processo."""
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


def auth_client() -> "Client":
    """Cliente NÃO cacheado para operações de auth (sign_in, sign_up).

    Cria uma nova instância a cada chamada para evitar compartilhar estado de
    sessão entre usuários distintos (o cliente cacheado é global ao processo).
    Usa SUPABASE_ANON_KEY quando disponível; cai no service_role como fallback.
    """
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_ANON_KEY") or _get_secret("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SupaNaoConfigurado("Credenciais do Supabase ausentes.")
    from supabase import create_client
    return create_client(url, key)


def configurado() -> bool:
    """Retorna True se as credenciais mínimas estão no ambiente."""
    return bool(_get_secret("SUPABASE_URL")) and bool(_get_secret("SUPABASE_SERVICE_KEY"))
