"""
Fatores de homogeneização — Método Comparativo Direto de Dados de Mercado
(tratamento por fatores), conforme metodologia da ABNT NBR 14653-2.

A homogeneização traz cada dado de mercado (comparável) à condição do imóvel
avaliando, multiplicando o valor unitário por fatores de ajuste.

⚠️ IMPORTANTE: os limites e tabelas aqui são referências de fontes técnicas
secundárias. ANTES de uso profissional, validar contra a NBR 14653 oficial e o
Manual de Avaliação de Imóveis da União 2024. Todos os fatores são editáveis na
tela, então o avaliador mantém o controle e a justificativa.
"""

# ---------------------------------------------------------------------------
# Critérios da NBR 14653-2 — TRATAMENTO POR FATORES (validados 2026-05-26 contra
# o texto da norma reproduzido no Manual de Avaliação de Imóveis da União 2024,
# Guia da Engenharia e Inteligência Urbana).
#
# Tabela "Grau de fundamentação no caso de utilização de tratamento por fatores"
# (4 itens). Pontuação: Grau III = 3 pts, II = 2, I = 1.
#   Item 1 — Caracterização do imóvel avaliando ........ (qualitativo)
#   Item 2 — Quantidade mínima de dados de mercado ..... 12 / 5 / 3
#   Item 3 — Identificação dos dados de mercado ........ (qualitativo)
#   Item 4 — Intervalo admissível do CONJUNTO de fatores 0,80–1,25 / 0,50–2,00 / 0,40–2,50
# Enquadramento: Grau III ≥10 pts (itens 2 e 4 no III); Grau II ≥6 pts (itens 2 e
# 4 ≥ II); Grau I ≥4 pts. ⚠️ Dispersão/coef. de variação NÃO é critério de grau
# no tratamento por fatores (isso é do tratamento científico/inferência).
# ---------------------------------------------------------------------------

# Item 2 — quantidade mínima de dados de mercado efetivamente utilizados
DADOS_GRAU_III = 12
DADOS_GRAU_II = 5
DADOS_GRAU_I = 3
MIN_COMPARAVEIS = DADOS_GRAU_I   # mínimo absoluto p/ qualquer grau (= Grau I)

# Item 4 — intervalo admissível de ajuste para o CONJUNTO de fatores (produtório)
PRODUTORIO_GRAU = {
    "III": (0.80, 1.25),
    "II": (0.50, 2.00),
    "I": (0.40, 2.50),
}
# Regra da norma: com menos de 5 dados, o intervalo admissível do conjunto é
# 0,80–1,25 (amostra pequena deve ser menos heterogênea).
PRODUTORIO_AMOSTRA_PEQUENA = (0.80, 1.25)

# Limite externo (Grau I) — fora disto o comparável é inaproveitável por fatores.
LIMITE_FATOR_MIN, LIMITE_FATOR_MAX = PRODUTORIO_GRAU["I"]

# Saneamento da amostra
DESVIO_SANEAMENTO = 0.30      # descarta quem estiver fora de ±30% da média
CAMPO_ARBITRIO = 0.15         # ±15% em torno da estimativa central (NBR)


# ---------------------------------------------------------------------------
# Fator Oferta / Fonte (elasticidade de oferta)
# Converte preço de anúncio em provável preço de transação.
# Faixa 0,80–1,20; quando indeterminado, adota-se 0,90 (desconto ~10%).
# ---------------------------------------------------------------------------
FATOR_OFERTA_PADRAO = 0.90
FATOR_OFERTA_MIN = 0.80
FATOR_OFERTA_MAX = 1.20


# ---------------------------------------------------------------------------
# Fator Conservação — Ross-Heidecke
# Foc = depreciação relativa entre o estado do comparável e o do avaliando.
# Tabela de coeficientes de depreciação (C) por estado de conservação.
# ---------------------------------------------------------------------------
# Coeficiente de depreciação Heidecke por estado (0 = novo; cresce com o desgaste)
ROSS_HEIDECKE = {
    "Novo": 0.0,
    "Entre novo e regular (pequenos reparos)": 0.0032,
    "Regular": 0.0252,
    "Entre regular e reparos simples": 0.0818,
    "Reparos simples": 0.1842,
    "Entre reparos simples e importantes": 0.3322,
    "Reparos importantes": 0.5260,
    "Entre reparos importantes e sem valor": 0.7512,
}


def fator_conservacao(estado_avaliando: str, estado_comparavel: str) -> float:
    """
    Razão de valor remanescente entre avaliando e comparável (Ross-Heidecke
    simplificado, sem componente de idade — a idade entra pelo fator próprio).
    Valor remanescente = 1 - C. Foc = (1 - C_avaliando) / (1 - C_comparavel).
    """
    c_av = ROSS_HEIDECKE.get(estado_avaliando, 0.0)
    c_cp = ROSS_HEIDECKE.get(estado_comparavel, 0.0)
    rem_cp = 1 - c_cp
    if rem_cp <= 0:
        return 1.0
    return (1 - c_av) / rem_cp


# ---------------------------------------------------------------------------
# Fator Área (homogeneização de área)
# Imóveis maiores tendem a ter menor valor unitário. Fórmula exponencial usual:
#   Fa = (Area_comparavel / Area_avaliando) ** expoente
# expoente típico entre 0,10 e 0,25 (zona/uso). Limite usual de ajuste.
# ---------------------------------------------------------------------------
EXPOENTE_AREA_PADRAO = 0.15


def fator_area(area_avaliando: float, area_comparavel: float,
               expoente: float = EXPOENTE_AREA_PADRAO) -> float:
    if not area_avaliando or not area_comparavel:
        return 1.0
    try:
        return (area_comparavel / area_avaliando) ** expoente
    except (ZeroDivisionError, ValueError):
        return 1.0


# ---------------------------------------------------------------------------
# Catálogo de fatores manuais/genéricos disponíveis na tela.
# O avaliador informa o valor de cada fator por comparável (ou usa o padrão).
# 'sentido' explica a leitura: fator > 1 valoriza o comparável em relação ao
# avaliando? Aqui adotamos a convenção: o fator MULTIPLICA o valor unitário do
# comparável para trazê-lo à condição do avaliando.
# ---------------------------------------------------------------------------
FATORES_DISPONIVEIS = [
    {"key": "f_oferta", "label": "Oferta/Fonte", "default": FATOR_OFERTA_PADRAO,
     "min": FATOR_OFERTA_MIN, "max": FATOR_OFERTA_MAX,
     "ajuda": "Desconto de elasticidade da oferta. 0,90 = ~10% de desconto do anúncio."},
    {"key": "f_localizacao", "label": "Localização", "default": 1.0, "min": 0.50, "max": 2.00,
     "ajuda": ">1 se o comparável é PIOR localizado que o avaliando (precisa subir o valor)."},
    {"key": "f_area", "label": "Área", "default": None, "min": 0.50, "max": 2.00,
     "ajuda": "Calculado automaticamente pela razão de áreas. Editável."},
    {"key": "f_conservacao", "label": "Conservação", "default": None, "min": 0.50, "max": 2.00,
     "ajuda": "Calculado por Ross-Heidecke a partir dos estados. Editável."},
    {"key": "f_padrao", "label": "Padrão construtivo", "default": 1.0, "min": 0.50, "max": 2.00,
     "ajuda": ">1 se o comparável tem padrão INFERIOR ao avaliando."},
    {"key": "f_outros", "label": "Outros (ajuste livre)", "default": 1.0, "min": 0.50, "max": 2.00,
     "ajuda": "Ajuste adicional justificado (vagas, andar, topografia, etc.)."},
]


def produtorio(fatores: dict) -> float:
    """Multiplica todos os fatores informados (ignora None e valores inválidos).

    Células vazias do data_editor podem chegar como NaN; um único NaN
    contaminaria o produto inteiro, então são descartadas (tratadas como
    'fator não informado' = 1,00).
    """
    import math as _math
    p = 1.0
    for v in fatores.values():
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if _math.isnan(f) or _math.isinf(f):
            continue
        p *= f
    return p


# Pontuação dos graus (NBR 14653-2)
GRAU_PONTOS = {"III": 3, "II": 2, "I": 1, "Insuficiente": 0}


def intervalo_produtorio(n_dados: int) -> dict:
    """
    Intervalos admissíveis do conjunto de fatores por grau, considerando a regra
    de amostra pequena (<5 dados ⇒ qualquer grau exige 0,80–1,25).
    """
    if n_dados < DADOS_GRAU_II:
        return {g: PRODUTORIO_AMOSTRA_PEQUENA for g in PRODUTORIO_GRAU}
    return dict(PRODUTORIO_GRAU)


def grau_por_quantidade(n_dados: int) -> str:
    """Item 2 — grau pelo nº de dados de mercado efetivamente utilizados."""
    if n_dados >= DADOS_GRAU_III:
        return "III"
    if n_dados >= DADOS_GRAU_II:
        return "II"
    if n_dados >= DADOS_GRAU_I:
        return "I"
    return "Insuficiente"


def grau_por_produtorio(produtorios: list[float], n_dados: int) -> str:
    """
    Item 4 — grau pelo pior (mais extremo) produtório de fatores da amostra,
    contra o intervalo admissível do conjunto (com a regra de amostra pequena).
    """
    if not produtorios:
        return "Insuficiente"
    lo, hi = min(produtorios), max(produtorios)
    intervalos = intervalo_produtorio(n_dados)
    for grau in ("III", "II", "I"):
        gmin, gmax = intervalos[grau]
        if lo >= gmin and hi <= gmax:
            return grau
    return "Insuficiente"
