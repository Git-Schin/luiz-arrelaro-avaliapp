"""Consulta de CEP brasileiro via ViaCEP (https://viacep.com.br).

Serviço gratuito, sem chave. Devolve um dict normalizado ou `None`.
"""
from __future__ import annotations

import requests
import streamlit as st

VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
TIMEOUT = 8


def _apenas_digitos(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 7)
def buscar_cep(cep: str) -> dict | None:
    """Consulta o CEP no ViaCEP.

    Devolve `{"logradouro", "bairro", "cidade", "uf", "cidade_uf"}` ou `None`
    se o CEP for inválido, não existir ou a chamada falhar.
    """
    digits = _apenas_digitos(cep)
    if len(digits) != 8:
        return None
    try:
        r = requests.get(VIACEP_URL.format(cep=digits), timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or data.get("erro"):
        return None
    cidade = (data.get("localidade") or "").strip()
    uf = (data.get("uf") or "").strip()
    cidade_uf = f"{cidade}/{uf}" if cidade and uf else (cidade or uf)
    return {
        "logradouro": (data.get("logradouro") or "").strip(),
        "bairro": (data.get("bairro") or "").strip(),
        "cidade": cidade,
        "uf": uf,
        "cidade_uf": cidade_uf,
    }
