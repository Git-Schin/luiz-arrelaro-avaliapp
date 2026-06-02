"""
Coleta/importação de comparáveis (pesquisa de mercado).

Objetivo (decisão 2026-05-26): importar comparáveis de forma SEGURA, sem scraping
de portais — o Luiz cola uma lista de texto ou sobe um CSV, revisa item a item e
decide o que entra no cálculo. Há uma interface de "coletor" extensível para, no
futuro, plugar uma API oficial ou outra fonte (mantendo o humano no circuito e o
cuidado com Termos de Uso).

Cada comparável importado vira um dict no schema da tabela de comparáveis:
    {descricao, fonte, origem, preco_total, area, conservacao}
Os fatores ficam para a tela (cálculo automático/manual).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata


# ---------------------------------------------------------------------------
# Parsing de números no formato brasileiro
# ---------------------------------------------------------------------------
def to_float(texto) -> float:
    """
    Converte string monetária/numérica BR em float.
    Aceita 'R$ 500.000,00', '1.250,50', '100', '100,5', '85 m²', '350.000'.
    """
    if texto is None:
        return 0.0
    if isinstance(texto, (int, float)):
        return float(texto)
    s = str(texto).strip().lower()
    s = s.replace("r$", "").replace("m²", "").replace("m2", "")
    s = re.sub(r"[^\d.,-]", "", s)            # mantém dígitos, ponto, vírgula, sinal
    if not s:
        return 0.0
    if "," in s and "." in s:                 # 1.250.000,50 -> ponto = milhar
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                            # 1250,50 -> vírgula decimal
        s = s.replace(",", ".")
    elif s.count(".") >= 1:
        # só pontos: '500.000' (milhar) vs '100.5' (decimal). Se o último grupo
        # tem 3 dígitos e há mais de um grupo, trata como milhar.
        partes = s.split(".")
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _norm(txt: str) -> str:
    """minúsculas sem acento, para casar cabeçalhos de coluna."""
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return txt.strip().lower()


# Sinônimos de cabeçalho -> campo do schema
_MAPA_COLUNAS = {
    "descricao": {"descricao", "imovel", "titulo", "endereco", "anuncio", "referencia", "obs"},
    "fonte": {"fonte", "portal", "site", "url", "link", "origem", "anunciante", "imobiliaria"},
    "preco_total": {"preco", "preco total", "valor", "valor total", "price", "preco do imovel"},
    "area": {"area", "area privativa", "area util", "area construida", "metragem", "m2", "tamanho"},
    "conservacao": {"conservacao", "estado", "estado de conservacao", "estado conservacao"},
}


def _campo_do_cabecalho(cabecalho: str) -> str | None:
    n = _norm(cabecalho)
    for campo, sinonimos in _MAPA_COLUNAS.items():
        if n in sinonimos:
            return campo
    return None


def _linha_para_comparavel(d: dict) -> dict:
    return {
        "descricao": str(d.get("descricao", "")).strip(),
        "fonte": str(d.get("fonte", "")).strip(),
        "origem": "automatica",
        "preco_total": to_float(d.get("preco_total")),
        "area": to_float(d.get("area")),
        "conservacao": str(d.get("conservacao", "")).strip(),
    }


# ---------------------------------------------------------------------------
# Importação de CSV
# ---------------------------------------------------------------------------
def importar_csv(conteudo) -> tuple[list[dict], list[str]]:
    """
    Lê CSV (vírgula ou ponto-e-vírgula). Mapeia cabeçalhos conhecidos.
    Retorna (comparaveis, avisos).
    """
    avisos: list[str] = []
    if isinstance(conteudo, bytes):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                texto = conteudo.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return [], ["Não foi possível decodificar o arquivo (use UTF-8)."]
    else:
        texto = str(conteudo)

    amostra = texto[:2048]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";" if amostra.count(";") >= amostra.count(",") else ","

    leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    if not leitor.fieldnames:
        return [], ["CSV vazio ou sem cabeçalho."]

    mapa = {col: _campo_do_cabecalho(col) for col in leitor.fieldnames}
    if "preco_total" not in mapa.values() or "area" not in mapa.values():
        avisos.append(
            "Cabeçalhos de preço e/ou área não reconhecidos. Use colunas como "
            "'preco'/'valor' e 'area'/'m2'. Colunas aceitas: "
            "descricao, fonte, preco, area, conservacao."
        )

    comparaveis = []
    for i, linha in enumerate(leitor, start=2):
        d = {}
        for col, campo in mapa.items():
            if campo:
                d[campo] = linha.get(col, "")
        c = _linha_para_comparavel(d)
        if c["preco_total"] <= 0 and c["area"] <= 0:
            continue  # linha vazia/inutilizável
        comparaveis.append(c)
    if not comparaveis and not avisos:
        avisos.append("Nenhuma linha com preço/área válidos encontrada.")
    return comparaveis, avisos


# ---------------------------------------------------------------------------
# Importação de texto colado (lista de anúncios, uma por linha)
# ---------------------------------------------------------------------------
_RE_PRECO = re.compile(r"r\$\s*([\d.,]+)", re.IGNORECASE)
_RE_AREA = re.compile(r"([\d.,]+)\s*m(?:²|2)\b", re.IGNORECASE)
_RE_NUM_GRANDE = re.compile(r"\b(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d{5,})\b")


def importar_texto(texto: str) -> tuple[list[dict], list[str]]:
    """
    Heurística para texto colado: cada linha não-vazia é um comparável. Extrai
    preço (R$ ...), área (... m²) e usa a linha como descrição. Linhas em que não
    se acha preço E área são ignoradas.
    """
    avisos: list[str] = []
    comparaveis = []
    for linha in (texto or "").splitlines():
        l = linha.strip()
        if not l:
            continue
        m_preco = _RE_PRECO.search(l)
        m_area = _RE_AREA.search(l)
        preco = to_float(m_preco.group(1)) if m_preco else 0.0
        area = to_float(m_area.group(1)) if m_area else 0.0
        if preco <= 0:  # tenta um número grande "solto" como preço
            m_num = _RE_NUM_GRANDE.search(l)
            if m_num:
                preco = to_float(m_num.group(1))
        if preco <= 0 or area <= 0:
            continue
        comparaveis.append({
            "descricao": l[:120], "fonte": "", "origem": "automatica",
            "preco_total": preco, "area": area, "conservacao": "",
        })
    if not comparaveis:
        avisos.append(
            "Não consegui extrair preço e área. Garanta que cada linha tenha o "
            "preço (ex.: R$ 450.000) e a área (ex.: 78 m²)."
        )
    return comparaveis, avisos


# ---------------------------------------------------------------------------
# Interface extensível de coletores (futuro: API oficial, etc.)
# ---------------------------------------------------------------------------
class Coletor:
    """Contrato para coletores de comparáveis. Implementar `buscar`."""
    nome = "base"
    ativo = False

    def buscar(self, **criterios) -> list[dict]:  # pragma: no cover - interface
        raise NotImplementedError


_COLETORES: dict[str, Coletor] = {}


def registrar_coletor(coletor: Coletor) -> None:
    _COLETORES[coletor.nome] = coletor


def coletores_ativos() -> list[Coletor]:
    return [c for c in _COLETORES.values() if c.ativo]
