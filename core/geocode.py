"""Geocoding leve via Nominatim (OpenStreetMap).

Sem chave de API, com cache em sessão (`@st.cache_data`) para respeitar o
rate-limit do serviço (~1 req/s). Falhas viram `None` — quem chama mostra
mensagem amigável.
"""
from __future__ import annotations

import re

import streamlit as st
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim

USER_AGENT = "avaliapp/1.0 (luiz arrelaro imoveis)"

# Centro da cidade do Luiz — usado como fallback inicial do mapa
CENTRO_PADRAO: tuple[float, float] = (-23.0053, -46.8392)  # Itatiba/SP

_RE_GEO = re.compile(
    r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$"
)


def parse_geo(s: str | None) -> tuple[float, float] | None:
    """Lê uma string 'lat, lng' e devolve (lat, lng) ou None."""
    if not s or not isinstance(s, str):
        return None
    m = _RE_GEO.match(s)
    if not m:
        return None
    try:
        lat = float(m.group(1).replace(",", "."))
        lng = float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return None
    return lat, lng


def format_geo(lat: float, lng: float) -> str:
    """Formata coordenadas em 'lat, lng' com 6 casas decimais."""
    return f"{lat:.6f}, {lng:.6f}"


def _montar_query(endereco: str, bairro: str, cidade_uf: str, cep: str) -> str:
    # "Itatiba/SP" confunde o Nominatim — vira "Itatiba, SP".
    cidade_uf = (cidade_uf or "").replace("/", ", ")
    partes = [p.strip() for p in (endereco, bairro, cidade_uf, cep) if p and p.strip()]
    return ", ".join(partes) + (", Brasil" if partes else "")


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def geocode_endereco(
    endereco: str = "",
    bairro: str = "",
    cidade_uf: str = "",
    cep: str = "",
) -> tuple[float, float] | None:
    """Geocodifica via Nominatim. Devolve (lat, lng) ou None.

    Cacheado por 24h para não bater no serviço a cada rerun.
    """
    query = _montar_query(endereco, bairro, cidade_uf, cep)
    if not query.strip(", "):
        return None
    try:
        geolocator = Nominatim(user_agent=USER_AGENT, timeout=8)
        loc = geolocator.geocode(query, language="pt-BR", country_codes="br")
    except GeopyError:
        return None
    except Exception:
        return None
    if loc is None:
        return None
    return float(loc.latitude), float(loc.longitude)


#: precisão aproximada do hit do geocoder
PRECISAO_LABEL = {
    "preciso":    "Endereço com número localizado.",
    "rua":        "Localizei a rua (sem número). Arraste o pin para o ponto exato.",
    "bairro":     "Localizei o bairro/região. Arraste o pin para o endereço.",
    "cidade":     "Só localizei a cidade. Arraste o pin para o endereço.",
}


def _tem_numero(endereco: str) -> bool:
    return any(ch.isdigit() for ch in (endereco or ""))


def _sem_numero(endereco: str) -> str:
    """Remove sequências de dígitos do final do logradouro (ex: 'Av X, 123' → 'Av X')."""
    import re
    return re.sub(r"[,\s]+\d+\s*[A-Za-z]?\s*$", "", endereco or "").strip().rstrip(",")


def geocode_em_cascata(
    endereco: str = "",
    bairro: str = "",
    cidade_uf: str = "",
    cep: str = "",
) -> tuple[float, float, str] | None:
    """Tenta variações progressivamente menos específicas até achar um hit.

    Devolve (lat, lng, precisao) onde precisao ∈ {"preciso","rua","bairro","cidade"},
    ou None se nada bateu. A ordem de tentativas é desenhada para o caso BR,
    onde Nominatim costuma falhar com número de casa que não está no OSM.
    """
    endereco = (endereco or "").strip()
    bairro = (bairro or "").strip()
    cidade_uf = (cidade_uf or "").strip()
    cep = (cep or "").strip()

    rua_sem_num = _sem_numero(endereco)
    tem_num = _tem_numero(endereco)

    # Ordem de queries: do mais específico para o mais aberto.
    tentativas: list[tuple[tuple[str, str, str, str], str]] = []
    if tem_num:
        tentativas.append(((endereco, bairro, cidade_uf, cep), "preciso"))
        tentativas.append(((endereco, bairro, cidade_uf, ""), "preciso"))
        tentativas.append(((rua_sem_num, bairro, cidade_uf, ""), "rua"))
    elif endereco:
        tentativas.append(((endereco, bairro, cidade_uf, cep), "rua"))
        tentativas.append(((endereco, bairro, cidade_uf, ""), "rua"))
    if bairro and cidade_uf:
        tentativas.append((("", bairro, cidade_uf, ""), "bairro"))
    if cep:
        tentativas.append((("", "", "", cep), "rua"))
    if cidade_uf:
        tentativas.append((("", "", cidade_uf, ""), "cidade"))

    vistos: set[tuple[str, str, str, str]] = set()
    for args, precisao in tentativas:
        if args in vistos or not any(a.strip() for a in args):
            continue
        vistos.add(args)
        res = geocode_endereco(*args)
        if res is not None:
            return (res[0], res[1], precisao)
    return None


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def reverse_geocode(lat: float, lng: float) -> str | None:
    """Devolve um endereço aproximado para as coordenadas, ou None."""
    try:
        geolocator = Nominatim(user_agent=USER_AGENT, timeout=8)
        loc = geolocator.reverse((lat, lng), language="pt-BR")
    except GeopyError:
        return None
    except Exception:
        return None
    return loc.address if loc else None
