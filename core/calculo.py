"""
Motor de cálculo da avaliação — Método Comparativo Direto (tratamento por fatores).

Fluxo:
  1. Para cada comparável: valor unitário (R$/m²) = preço / área.
  2. Homogeneização: V_hom = V_unit * produtório dos fatores.
  3. Saneamento: descarta comparáveis fora de ±30% da média (iterativo).
  4. Estimativa central = média dos homogeneizados válidos.
  5. Valor do avaliando = estimativa * área do avaliando.
  6. Campo de arbítrio = ±15%.
  7. Grau de fundamentação pela tabela do TRATAMENTO POR FATORES da NBR 14653-2.

Grau de fundamentação (NBR 14653-2, tratamento por fatores — validado 2026-05-26):
os 4 itens da norma são pontuados (III=3, II=2, I=1) e enquadrados. O app avalia
automaticamente os itens 2 (quantidade de dados) e 4 (intervalo do conjunto de
fatores); os itens 1 (caracterização) e 3 (identificação dos dados) são
qualitativos e dependem da documentação — o avaliador os informa (padrão Grau II).
O coeficiente de variação é exibido como informação, mas NÃO entra no grau (CV é
critério do tratamento científico, não do tratamento por fatores).
"""
from dataclasses import dataclass, field
from statistics import mean, pstdev
from . import fatores as F


@dataclass
class Comparavel:
    descricao: str = ""
    fonte: str = ""              # portal, contato, anúncio...
    link: str = ""               # URL do anúncio (preenchido pela busca da IA)
    origem: str = "manual"       # "manual" | "automatica"
    incluir: bool = True         # o Luiz decide se entra no cálculo
    preco_total: float = 0.0
    area: float = 0.0
    conservacao: str = ""        # estado de conservação (entra no fator automático)
    fatores: dict = field(default_factory=dict)
    # preenchidos pelo cálculo:
    valor_unitario: float = 0.0
    fator_total: float = 1.0
    valor_homogeneizado: float = 0.0
    valido: bool = True          # passou no saneamento
    motivo_descarte: str = ""


@dataclass
class ResultadoAvaliacao:
    valor_unitario_medio: float = 0.0     # R$/m² homogeneizado
    area_avaliando: float = 0.0
    valor_total: float = 0.0
    valor_min_arbitrio: float = 0.0
    valor_max_arbitrio: float = 0.0
    n_comparaveis_usados: int = 0
    coef_variacao: float = 0.0            # dispersão dos homogeneizados (%) — informativo
    grau_fundamentacao: str = "—"
    grau_pontos: int = 0                  # soma dos pontos dos 4 itens (máx. 12)
    graus_itens: dict = field(default_factory=dict)  # grau por item da tabela
    avisos: list = field(default_factory=list)
    comparaveis: list = field(default_factory=list)


def _homogeneizar(comparaveis: list[Comparavel]) -> None:
    """Calcula valor unitário, fator total e valor homogeneizado (in-place)."""
    for c in comparaveis:
        c.valor_unitario = (c.preco_total / c.area) if c.area else 0.0
        c.fator_total = F.produtorio(c.fatores)
        c.valor_homogeneizado = c.valor_unitario * c.fator_total


def _sanear(comparaveis: list[Comparavel]) -> list[Comparavel]:
    """
    Descarta iterativamente os homogeneizados fora de ±30% da média.
    Retorna a lista dos válidos. Marca motivo_descarte nos demais.
    """
    validos = [c for c in comparaveis if c.incluir and c.valor_homogeneizado > 0]
    for c in comparaveis:
        if c.incluir and c.valor_homogeneizado <= 0:
            c.valido = False
            c.motivo_descarte = "Preço ou área inválidos"

    # A cada passo remove o ELEMENTO MAIS DISCREPANTE (não o primeiro encontrado),
    # recalculando a média, enquanto houver alguém fora de ±30% e mantendo o mínimo.
    while len(validos) > F.MIN_COMPARAVEIS:
        m = mean(c.valor_homogeneizado for c in validos)
        if not m:
            break
        pior = max(validos, key=lambda c: abs(c.valor_homogeneizado - m) / m)
        desvio = abs(pior.valor_homogeneizado - m) / m
        if desvio > F.DESVIO_SANEAMENTO:
            pior.valido = False
            pior.motivo_descarte = (
                f"Fora de ±{int(F.DESVIO_SANEAMENTO*100)}% da média (desvio {desvio*100:.0f}%)"
            )
            validos.remove(pior)
        else:
            break
    for c in validos:
        c.valido = True
    return validos


_GRAU_ROTULO = {
    "III": "Grau III (rigoroso)",
    "II": "Grau II (normal)",
    "I": "Grau I (expedito)",
    "Insuficiente": "Insuficiente",
}


def _grau_fundamentacao(n: int, produtorios: list[float],
                        grau_caracterizacao: str = "II",
                        grau_identificacao: str = "II") -> tuple[str, int, dict, list[str]]:
    """
    Enquadramento do grau de fundamentação no TRATAMENTO POR FATORES (NBR 14653-2).
    Avalia os 4 itens da tabela, pontua (III=3, II=2, I=1) e enquadra. Itens 2 e 4
    são automáticos; itens 1 e 3 são informados (padrão Grau II) por dependerem da
    documentação. Retorna (rótulo, pontos, graus_por_item, avisos).
    """
    avisos = []
    g_qtd = F.grau_por_quantidade(n)
    g_prod = F.grau_por_produtorio(produtorios, n)
    graus = {
        "1_caracterizacao": grau_caracterizacao,
        "2_quantidade": g_qtd,
        "3_identificacao": grau_identificacao,
        "4_conjunto_fatores": g_prod,
    }

    if n < F.MIN_COMPARAVEIS:
        avisos.append(
            f"São necessários no mínimo {F.MIN_COMPARAVEIS} comparáveis válidos (há {n})."
        )
        return "Insuficiente", 0, graus, avisos

    pts = F.GRAU_PONTOS
    pontos = sum(pts[g] for g in graus.values())

    if g_prod == "Insuficiente":
        lo = min(produtorios) if produtorios else 0
        hi = max(produtorios) if produtorios else 0
        intervalos = F.intervalo_produtorio(n)
        gi_min, gi_max = intervalos["I"]
        avisos.append(
            f"Produtório de fatores fora do intervalo admissível ({gi_min:.2f}–{gi_max:.2f}; "
            f"observado {lo:.2f}–{hi:.2f}) — grau insuficiente. Revise os fatores/comparáveis."
        )
        return "Insuficiente", pontos, graus, avisos

    # Enquadramento (do maior grau para o menor)
    if (pontos >= 10 and g_qtd == "III" and g_prod == "III"
            and pts[grau_caracterizacao] >= 2 and pts[grau_identificacao] >= 2):
        grau = "III"
    elif (pontos >= 6 and pts[g_qtd] >= 2 and pts[g_prod] >= 2
          and all(pts[g] >= 1 for g in graus.values())):
        grau = "II"
    elif pontos >= 4 and all(pts[g] >= 1 for g in graus.values()):
        grau = "I"
    else:
        grau = "Insuficiente"

    if n < F.DADOS_GRAU_II:
        avisos.append(
            f"Amostra pequena ({n} dados, <{F.DADOS_GRAU_II}): o conjunto de fatores deve "
            f"ficar em {F.PRODUTORIO_AMOSTRA_PEQUENA[0]:.2f}–{F.PRODUTORIO_AMOSTRA_PEQUENA[1]:.2f}."
        )
    avisos.append(
        "Itens 1 (caracterização) e 3 (identificação dos dados) assumidos como "
        f"{grau_caracterizacao}/{grau_identificacao} — confirme conforme a documentação anexada."
    )
    return _GRAU_ROTULO[grau], pontos, graus, avisos


def calcular(comparaveis: list[Comparavel], area_avaliando: float,
             grau_caracterizacao: str = "II",
             grau_identificacao: str = "II") -> ResultadoAvaliacao:
    res = ResultadoAvaliacao(area_avaliando=area_avaliando, comparaveis=comparaveis)

    _homogeneizar(comparaveis)

    # alerta de fatores fora do limite externo (Grau I = 0,40–2,50)
    for c in comparaveis:
        if c.incluir and not (F.LIMITE_FATOR_MIN <= c.fator_total <= F.LIMITE_FATOR_MAX):
            res.avisos.append(
                f"Comparável '{c.descricao or c.fonte or '?'}' tem produtório de fatores "
                f"{c.fator_total:.2f}, fora do limite admissível {F.LIMITE_FATOR_MIN:.2f}–"
                f"{F.LIMITE_FATOR_MAX:.2f} (Grau I)."
            )

    validos = _sanear(comparaveis)
    res.n_comparaveis_usados = len(validos)

    if not validos:
        res.grau_fundamentacao = "Insuficiente"
        res.avisos.append("Nenhum comparável válido após o saneamento.")
        return res

    valores = [c.valor_homogeneizado for c in validos]
    res.valor_unitario_medio = mean(valores)
    res.coef_variacao = (pstdev(valores) / res.valor_unitario_medio * 100) if len(valores) > 1 else 0.0

    if area_avaliando:
        res.valor_total = res.valor_unitario_medio * area_avaliando
        res.valor_min_arbitrio = res.valor_total * (1 - F.CAMPO_ARBITRIO)
        res.valor_max_arbitrio = res.valor_total * (1 + F.CAMPO_ARBITRIO)
    else:
        res.avisos.append("Área do imóvel avaliando não informada — valor total não calculado.")

    produtorios = [c.fator_total for c in validos]
    grau, pontos, graus_itens, avisos = _grau_fundamentacao(
        res.n_comparaveis_usados, produtorios, grau_caracterizacao, grau_identificacao
    )
    res.grau_fundamentacao = grau
    res.grau_pontos = pontos
    res.graus_itens = graus_itens
    res.avisos.extend(avisos)
    return res


def formatar_brl(valor: float) -> str:
    """Formata número como moeda brasileira (R$ 1.234.567,89)."""
    if valor is None:
        return "—"
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"
