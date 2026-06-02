"""
Wizard de Nova Avaliação — definição dos passos, renderização do stepper
e validação dos obrigatórios por passo.

Cinco passos:
  1 · Identificação      (tipo + solicitante + finalidade + localização)
  2 · Documentos & fotos (OCR matrícula/IPTU + galeria de fotos)
  3 · Características    (form dinâmico do tipo de imóvel)
  4 · Comparáveis        (IA / import / manual + fundamentação qualitativa)
  5 · Cálculo & entrega  (calcular + resultado + IA pós-cálculo + salvar/PDFs)

A página `pages/1_Nova_Avaliacao.py` lê PASSOS daqui e renderiza um por vez.
"""
from __future__ import annotations

import streamlit as st

from core import tipos_imovel as TI

# ----------------------------------------------------------------------------
# Definição dos passos
# ----------------------------------------------------------------------------
PASSOS: list[dict] = [
    {"id": 1, "key": "identificacao", "titulo": "Identificação",   "icone": "👤"},
    {"id": 2, "key": "documentos",    "titulo": "Documentos & fotos", "icone": "📄"},
    {"id": 3, "key": "caracteristicas", "titulo": "Características", "icone": "🏠"},
    {"id": 4, "key": "comparaveis",   "titulo": "Comparáveis",     "icone": "🏷️"},
    {"id": 5, "key": "calculo",       "titulo": "Cálculo & entrega", "icone": "📊"},
]
TOTAL_PASSOS = len(PASSOS)

# Campos do GRUPO_IDENTIFICACAO/GRUPO_LOCALIZACAO que são obrigatórios no passo 1.
# (Mantido aqui em vez de derivar do TI.GRUPO_*: os obrigatórios variam por contexto
# do wizard e algumas chaves só fazem sentido em conjunto.)
OBRIGATORIOS_IDENTIFICACAO = [
    ("finalidade",  "Finalidade da avaliação"),
    ("solicitante", "Solicitante / Cliente"),
    ("endereco",    "Logradouro / Rua"),
    ("bairro",      "Bairro"),
    ("cidade_uf",   "Cidade/UF"),
]


# ----------------------------------------------------------------------------
# Estado
# ----------------------------------------------------------------------------
def passo_atual() -> int:
    """Passo atual (1..5). Inicia em 1."""
    return int(st.session_state.get("wizard_passo", 1))


def ir_para(passo: int) -> None:
    """Salta para um passo do wizard (clamped). Dispara rerun."""
    p = max(1, min(TOTAL_PASSOS, int(passo)))
    if p != passo_atual():
        st.session_state["wizard_passo"] = p
        st.rerun()


# ----------------------------------------------------------------------------
# Validação
# ----------------------------------------------------------------------------
def _vazio(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (int, float)):
        return float(v) == 0.0
    return False


def validar_passo(passo: int, dados: dict) -> list[str]:
    """Retorna a lista de rótulos de campos OBRIGATÓRIOS pendentes no passo.

    Não inclui avisos suaves (passo 2 não tem obrigatório).
    """
    imovel = dados.get("imovel") or {}
    pendentes: list[str] = []

    if passo == 1:
        for key, rotulo in OBRIGATORIOS_IDENTIFICACAO:
            if _vazio(imovel.get(key)):
                pendentes.append(rotulo)

    elif passo == 3:
        tipo_key = dados.get("tipo_imovel")
        if not tipo_key or tipo_key not in TI.TIPOS_IMOVEL:
            pendentes.append("Tipo de imóvel (passo 1)")
        else:
            tipo_def = TI.get_tipo(tipo_key)
            # Pega obrigatórios apenas do grupo "Características" — Identificação
            # e Localização são cobertos pelo passo 1.
            for grupo in tipo_def["grupos"]:
                if grupo["titulo"].lower().startswith(("caracter")):
                    for campo in grupo["campos"]:
                        if campo.get("obrigatorio") and _vazio(imovel.get(campo["key"])):
                            pendentes.append(campo["label"])

    elif passo == 4:
        # Exige pelo menos 1 comparável marcado "Incluir" com preço e área.
        usados = [
            c for c in (dados.get("comparaveis") or [])
            if c.get("incluir") and (c.get("preco_total") or 0) > 0
            and (c.get("area") or 0) > 0
        ]
        if not usados:
            pendentes.append("Ao menos 1 comparável incluído com preço e área")

    return pendentes


def validar_completo(dados: dict) -> dict[int, list[str]]:
    """Devolve {passo: [pendências]} para todos os passos com pendências."""
    out: dict[int, list[str]] = {}
    for p in PASSOS:
        pend = validar_passo(p["id"], dados)
        if pend:
            out[p["id"]] = pend
    return out


# ----------------------------------------------------------------------------
# Renderização do stepper
# ----------------------------------------------------------------------------
def render_stepper(dados: dict | None = None) -> None:
    """Pinta a barra de passos no topo da página. Cada pílula é clicável."""
    atual = passo_atual()
    pendencias = validar_completo(dados or {})
    cols = st.columns(TOTAL_PASSOS, gap="small")
    for i, passo in enumerate(PASSOS):
        with cols[i]:
            tem_pend = bool(pendencias.get(passo["id"]))
            if passo["id"] == atual:
                tipo = "primary"
                rotulo = f"**{passo['icone']} {passo['id']} · {passo['titulo']}**"
            else:
                tipo = "secondary"
                marca = " ⚠️" if tem_pend else ""
                rotulo = f"{passo['icone']} {passo['id']} · {passo['titulo']}{marca}"
            if st.button(rotulo, key=f"step_btn_{passo['id']}",
                         use_container_width=True, type=tipo):
                ir_para(passo["id"])
    st.divider()


# ----------------------------------------------------------------------------
# Barra de navegação inferior (Anterior / Próximo)
# ----------------------------------------------------------------------------
def render_nav_inferior(
    *,
    on_avancar=None,
    on_voltar=None,
    label_avancar: str = "Próximo →",
    label_voltar: str = "← Anterior",
    desabilitar_avancar: bool = False,
) -> None:
    """Botões Anterior/Próximo no rodapé do passo. Chama os callbacks (que
    geralmente persistem rascunho) e em seguida muda o passo via ir_para()."""
    atual = passo_atual()
    st.divider()
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if atual > 1 and st.button(label_voltar, use_container_width=True,
                                    key=f"nav_voltar_{atual}"):
            if on_voltar:
                on_voltar()
            ir_para(atual - 1)
    with c3:
        if atual < TOTAL_PASSOS:
            if st.button(label_avancar, use_container_width=True, type="primary",
                         key=f"nav_avancar_{atual}", disabled=desabilitar_avancar):
                if on_avancar:
                    on_avancar()
                ir_para(atual + 1)
