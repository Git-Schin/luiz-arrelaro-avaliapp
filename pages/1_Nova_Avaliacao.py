"""Nova Avaliação — wizard em 5 passos.

Passos: 1·Identificação · 2·Documentos & fotos · 3·Características ·
        4·Comparáveis · 5·Cálculo & entrega
"""
import math
from datetime import datetime

import pandas as pd
import streamlit as st

from core import anexos as AN, coleta as CO, db, fatores as F, ia as IA
from core import cep as CEP
from core import geocode as GEO
from core import tipos_imovel as TI
from core import wizard as WZ
from core.calculo import Comparavel, calcular, formatar_brl
from core import pdf as PDFGEN

# ============================================================================
# RESET COMPLETO — "Limpar / nova avaliação"
# ============================================================================
_RESET_PREFIXOS = (
    "f_", "ia_", "ocr", "editor_comparaveis", "rmfoto_", "csv_", "txt_", "btn_",
    "step_btn_", "nav_", "wizard_", "_pend_", "_p_",
)
_RESET_EXATOS = {
    "edicao", "edicao_id", "ultimo_resultado", "ultimo_resultado_obj",
    "comparaveis_importados", "ocr_sugestoes", "ia_analise", "ia_textos",
    "fotos_imovel", "fotos_uploader", "import_rev",
    "rascunho_salvo_em", "tipo_imovel_sel", "_geo_precisao", "_geo_auto_tentado",
}
if st.session_state.pop("_resetar_form", False):
    for _k in list(st.session_state.keys()):
        if _k in _RESET_EXATOS or _k.startswith(_RESET_PREFIXOS):
            del st.session_state[_k]
    # Limpa o id do rascunho da URL — uma nova avaliação deve começar do zero.
    try:
        st.query_params.clear()
    except Exception:
        pass

# ============================================================================
# RECUPERAÇÃO DE EMERGÊNCIA — rascunho via URL (?r=ID)
# ============================================================================
# O Streamlit Cloud pode descartar o `session_state` quando o usuário fica
# inativo (ou o processo do app é reciclado). Para que o usuário não perca
# o que digitou, o id do rascunho atual também vive na URL como `?r=ID`.
# Se chegamos aqui sem `edicao` no session_state mas a URL tem `r`, buscamos
# o rascunho do banco e populamos tudo de volta.
_qp_r = st.query_params.get("r")
if _qp_r and not st.session_state.get("edicao"):
    try:
        _row = db.obter(int(_qp_r))
    except Exception:
        _row = None
    if _row and _row.get("status") == db.STATUS_RASCUNHO:
        _dados = _row.get("dados", {}) or {}
        _dados["_passo_atual"] = _row.get("passo_atual") or 1
        st.session_state["edicao"] = _dados
        st.session_state["edicao_id"] = _row["id"]
        st.session_state.pop("_edic_hidratado", None)
        st.session_state.pop("wizard_passo", None)

# ============================================================================
# EDIÇÃO (vinda do Histórico ou da URL) — pré-carrega valores
# ============================================================================
edic = st.session_state.get("edicao")
edic_id = st.session_state.get("edicao_id")

# Quando uma avaliação é reaberta, hidratamos o session_state com os valores
# salvos, para os widgets aparecerem preenchidos. Faz isso uma vez só.
if edic and not st.session_state.get("_edic_hidratado"):
    edic_imovel = edic.get("imovel", {})
    edic_tipo = edic.get("tipo_imovel")
    if edic_tipo:
        st.session_state["tipo_imovel_sel"] = edic_tipo
    for grupo in [TI.GRUPO_IDENTIFICACAO, TI.GRUPO_LOCALIZACAO]:
        for campo in grupo["campos"]:
            v = edic_imovel.get(campo["key"])
            if v not in (None, ""):
                wk = f"f_ident_{campo['key']}"
                st.session_state[wk] = v
                st.session_state[f"_p_{wk}"] = v  # shadow para sobreviver entre passos
    if edic_tipo and edic_tipo in TI.TIPOS_IMOVEL:
        for grupo in TI.get_tipo(edic_tipo)["grupos"]:
            if grupo["titulo"].lower().startswith("caracter"):
                for campo in grupo["campos"]:
                    v = edic_imovel.get(campo["key"])
                    if v not in (None, ""):
                        wk = f"f_{edic_tipo}_{campo['key']}"
                        st.session_state[wk] = v
                        st.session_state[f"_p_{wk}"] = v
    # Reabrir no passo onde a avaliação parou (rascunho) ou no resumo (concluída)
    st.session_state.setdefault("wizard_passo", int(edic.get("_passo_atual") or 5))
    st.session_state["_edic_hidratado"] = True

# Pending values genérico — qualquer ação (mapa, busca de CEP, etc.) que
# precise atualizar um widget já criado escreve em `_pend_<widget_key>` e
# dispara rerun; aqui, ANTES de qualquer widget renderizar, aplicamos.
# (Streamlit proíbe modificar st.session_state[key] depois que o widget
# com aquela key foi instanciado no run atual.)
for _pk in [k for k in list(st.session_state.keys()) if k.startswith("_pend_")]:
    _target = _pk[len("_pend_"):]
    _val = st.session_state.pop(_pk)
    st.session_state[_target] = _val
    # Espelha na shadow se for widget de form (f_*), para sobreviver a passos
    if _target.startswith("f_"):
        st.session_state[f"_p_{_target}"] = _val

st.title("📝 Nova avaliação")
if edic_id:
    st.info(f"✏️ Editando a avaliação #{edic_id}.")

# ============================================================================
# TIPO DE IMÓVEL — escolhido no passo 1, lido em todos os outros passos
# ============================================================================
tipos = TI.listar_tipos()
tipo_keys = [k for k, _ in tipos]
tipo_labels = [r for _, r in tipos]
tipo_key = st.session_state.get("tipo_imovel_sel", tipo_keys[0])
if tipo_key not in tipo_keys:
    tipo_key = tipo_keys[0]
tipo_def = TI.get_tipo(tipo_key)


# ============================================================================
# Helpers
# ============================================================================
def _get_field(wkey: str):
    """Lê valor do session_state, com fallback para a "shadow key" `_p_<wkey>`.

    Streamlit faz GC do session_state[wkey] quando o widget não é renderizado
    em um run (caso típico no wizard: estamos no passo 4 e os widgets do passo
    1 não existem neste run). A shadow key NÃO é uma widget key — por isso
    o Streamlit não a apaga, e podemos restaurar a partir dela.
    """
    v = st.session_state.get(wkey)
    if v in (None, "", 0, False):
        v = st.session_state.get(f"_p_{wkey}")
    return v


def _construir_imovel() -> dict:
    """Lê o session_state (com fallback pra shadow) e retorna o dict do imóvel."""
    imovel = {}
    for grupo in [TI.GRUPO_IDENTIFICACAO, TI.GRUPO_LOCALIZACAO]:
        for campo in grupo["campos"]:
            v = _get_field(f"f_ident_{campo['key']}")
            if v not in (None, "", 0, False):
                imovel[campo["key"]] = v
    for grupo in tipo_def["grupos"]:
        if grupo["titulo"].lower().startswith("caracter"):
            for campo in grupo["campos"]:
                v = _get_field(f"f_{tipo_key}_{campo['key']}")
                if v not in (None, "", 0, False):
                    imovel[campo["key"]] = v
    return imovel


def _imovel_detalhado(imovel: dict) -> list:
    """Lista de (rótulo, valor) por grupo, p/ PDF."""
    out = []
    for grupo in tipo_def["grupos"]:
        linhas = []
        for campo in grupo["campos"]:
            v = imovel.get(campo["key"])
            if v not in (None, "", 0, False):
                u = f" {campo['unidade']}" if campo.get("unidade") else ""
                linhas.append((campo["label"], f"{v}{u}"))
        if linhas:
            out.append(linhas)
    return out


def _render_campo(campo: dict, prefixo: str) -> None:
    """Renderiza um campo do form; valor fica em session_state[wkey] e é
    espelhado em `_p_<wkey>` (shadow) para sobreviver a passos onde o widget
    não é renderizado (Streamlit faz GC dos values dos widgets sumiram do tree)."""
    key = campo["key"]
    label = campo["label"] + (" *" if campo.get("obrigatorio") else "")
    if campo.get("unidade"):
        label += f" ({campo['unidade']})"
    ajuda = campo.get("ajuda")
    wkey = f"{prefixo}_{key}"
    pkey = f"_p_{wkey}"
    tipo = campo["tipo"]
    default = campo.get("default")

    # 1) Restaura da shadow se o widget está vindo sem valor neste run
    #    (típico após o GC do Streamlit ao trocar de passo).
    if wkey not in st.session_state and pkey in st.session_state:
        st.session_state[wkey] = st.session_state[pkey]

    # 2) Se ainda não há valor, semeia com o default.
    if wkey not in st.session_state and default not in (None, ""):
        st.session_state[wkey] = default

    # on_change roda toda vez que o widget perde foco/submete: salva shadow
    # E persiste o rascunho no Supabase. Garante que NADA seja perdido se o
    # session_state for descartado pelo Streamlit Cloud entre interações.
    _kwargs = {"on_change": _on_change_field, "args": (wkey,)}

    if tipo == "number":
        if wkey in st.session_state and not isinstance(st.session_state[wkey], (int, float)):
            try:
                st.session_state[wkey] = float(st.session_state[wkey])
            except (TypeError, ValueError):
                st.session_state[wkey] = 0.0
        st.number_input(label, min_value=0.0, step=1.0, help=ajuda, key=wkey, **_kwargs)
    elif tipo == "select":
        opts = campo["opcoes"]
        if wkey not in st.session_state or st.session_state[wkey] not in opts:
            st.session_state[wkey] = opts[0]
        st.selectbox(label, opts, help=ajuda, key=wkey, **_kwargs)
    elif tipo == "checkbox":
        if wkey not in st.session_state:
            st.session_state[wkey] = False
        st.checkbox(label, help=ajuda, key=wkey, **_kwargs)
    elif tipo == "textarea":
        st.text_area(label, help=ajuda, key=wkey, **_kwargs)
    else:
        st.text_input(label, help=ajuda, key=wkey, **_kwargs)

    # 3) Espelha o valor atual na shadow. Como `_p_<wkey>` NÃO é uma widget
    #    key, o Streamlit não faz GC dela quando trocamos de passo.
    if wkey in st.session_state:
        st.session_state[pkey] = st.session_state[wkey]


def _rotulo_campo(key: str) -> str:
    """Devolve o label amigável do campo (procura em Identificação/Localização/tipo atual)."""
    for grupo in (TI.GRUPO_IDENTIFICACAO, TI.GRUPO_LOCALIZACAO):
        for c in grupo["campos"]:
            if c["key"] == key:
                return c["label"]
    if tipo_key in TI.TIPOS_IMOVEL:
        for grupo in TI.get_tipo(tipo_key)["grupos"]:
            for c in grupo["campos"]:
                if c["key"] == key:
                    return c["label"]
    return key


def _prefixo_widget(key: str) -> str:
    """Onde o valor do campo deve cair: `f_ident` (passo 1) ou `f_<tipo>` (passo 3)."""
    for c in TI.GRUPO_IDENTIFICACAO["campos"] + TI.GRUPO_LOCALIZACAO["campos"]:
        if c["key"] == key:
            return "f_ident"
    return f"f_{tipo_key}"


def _aceitar_sugestoes_ocr(keys: list[str]) -> None:
    """Aplica via pending os campos escolhidos e os remove de ocr_sugestoes."""
    sugest = dict(st.session_state.get("ocr_sugestoes") or {})
    for k in keys:
        v = sugest.get(k)
        if v in (None, ""):
            sugest.pop(k, None)
            continue
        widget_key = f"{_prefixo_widget(k)}_{k}"
        st.session_state[f"_pend_{widget_key}"] = v
        sugest.pop(k, None)
    if sugest:
        st.session_state["ocr_sugestoes"] = sugest
    else:
        st.session_state.pop("ocr_sugestoes", None)


def _ignorar_sugestao_ocr(key: str) -> None:
    sugest = dict(st.session_state.get("ocr_sugestoes") or {})
    sugest.pop(key, None)
    if sugest:
        st.session_state["ocr_sugestoes"] = sugest
    else:
        st.session_state.pop("ocr_sugestoes", None)


def _render_sugestoes_ocr() -> None:
    """Painel de revisão das sugestões da IA — aceitar/ignorar campo a campo."""
    sugest = st.session_state.get("ocr_sugestoes") or {}
    if not sugest:
        return
    st.markdown(f"##### 🤖 Sugestões da IA — {len(sugest)} campo(s)")
    st.caption(
        "A IA leu o documento e sugere estes valores. Aceite os corretos; o que "
        "você ignorar não sobrescreve seu preenchimento manual."
    )
    cg1, cg2 = st.columns(2)
    with cg1:
        if st.button("✅ Aceitar todas", use_container_width=True,
                     type="primary", key="ocr_aceitar_todas"):
            _aceitar_sugestoes_ocr(list(sugest.keys()))
            st.toast("Sugestões aplicadas.", icon="✅")
            st.rerun()
    with cg2:
        if st.button("🗑️ Descartar todas", use_container_width=True,
                     key="ocr_descartar_todas"):
            st.session_state.pop("ocr_sugestoes", None)
            st.rerun()

    for k in list(sugest.keys()):
        valor_ia = sugest[k]
        rotulo = _rotulo_campo(k)
        atual = _get_field(f"{_prefixo_widget(k)}_{k}")
        atual_str = "" if atual in (None, "", 0, 0.0, False) else str(atual)
        with st.container(border=True):
            st.markdown(f"**{rotulo}**")
            if atual_str:
                st.markdown(
                    f"Atual: `{atual_str}` &nbsp;→&nbsp; IA: `{valor_ia}`",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"_(vazio)_ &nbsp;→&nbsp; IA: `{valor_ia}`",
                            unsafe_allow_html=True)
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("✓ Aceitar", key=f"ocr_aceitar_{k}",
                             use_container_width=True, type="primary"):
                    _aceitar_sugestoes_ocr([k])
                    st.rerun()
            with cb2:
                if st.button("✕ Ignorar", key=f"ocr_ignorar_{k}",
                             use_container_width=True):
                    _ignorar_sugestao_ocr(k)
                    st.rerun()


def _render_busca_cep(campo_cep: dict) -> None:
    """Linha 'CEP + botão Buscar'. Ao clicar, ViaCEP preenche logradouro,
    bairro e cidade/UF via pending; depois geocoda para o pin do mapa."""
    c1, c2 = st.columns([2, 1])
    with c1:
        _render_campo(campo_cep, "f_ident")
    with c2:
        # Espaço fantasma para alinhar o botão com o input (que tem label em cima)
        st.markdown('<div style="height: 1.85rem"></div>', unsafe_allow_html=True)
        clicou = st.button("🔍 Buscar pelo CEP", use_container_width=True,
                           key="btn_busca_cep")
    if not clicou:
        return
    cep_val = (_get_field("f_ident_cep") or "").strip()
    if not cep_val:
        st.warning("Digite um CEP antes de buscar.")
        return
    with st.spinner("Consultando CEP..."):
        info = CEP.buscar_cep(cep_val)
    if info is None:
        st.warning("CEP inválido ou não encontrado. Verifique e tente de novo.")
        return
    if info["logradouro"]:
        st.session_state["_pend_f_ident_endereco"] = info["logradouro"]
    if info["bairro"]:
        st.session_state["_pend_f_ident_bairro"] = info["bairro"]
    if info["cidade_uf"]:
        st.session_state["_pend_f_ident_cidade_uf"] = info["cidade_uf"]
    rotulo = info["cidade_uf"] or "endereço"
    st.toast(f"CEP localizado em {rotulo}. Falta só o número.", icon="✅")
    st.rerun()


def _autopreencher_geo() -> None:
    """Geocoda lat/lng automaticamente quando CEP + logradouro + número + bairro
    + cidade/UF estão TODOS preenchidos e o campo `geo` está vazio.

    Roda no passo 1, no fim do bloco de Localização. Não repete a busca para
    os mesmos inputs (cache em `_geo_auto_tentado`).
    """
    if (_get_field("f_ident_geo") or "").strip():
        return  # geo já preenchido (manual, CEP ou auto anterior)
    cep = (_get_field("f_ident_cep") or "").strip()
    logr = (_get_field("f_ident_endereco") or "").strip()
    num = (_get_field("f_ident_numero") or "").strip()
    bairro = (_get_field("f_ident_bairro") or "").strip()
    cidade = (_get_field("f_ident_cidade_uf") or "").strip()
    if not all([cep, logr, num, bairro, cidade]):
        return
    inputs = (cep, logr, num, bairro, cidade)
    if st.session_state.get("_geo_auto_tentado") == inputs:
        return
    st.session_state["_geo_auto_tentado"] = inputs
    endereco_full = f"{logr} {num}".strip()
    with st.spinner("Calculando coordenadas do endereço..."):
        hit = GEO.geocode_em_cascata(endereco_full, bairro, cidade, cep)
    if hit is None:
        return
    lat, lng, precisao = hit
    st.session_state["_pend_f_ident_geo"] = GEO.format_geo(lat, lng)
    st.session_state["_geo_precisao"] = precisao
    st.rerun()


# ============================================================================
# Autosalvar rascunho
# ============================================================================
def _lista_para_df_comparaveis(lista: list[dict], estado_default: str = "Regular"):
    """Converte lista de dicts (como persistido no banco) em DataFrame
    no formato esperado pelo data_editor do passo 4."""
    rows = []
    for c in lista or []:
        fat = c.get("fatores", {}) or {}
        rows.append({
            "Descrição": c.get("descricao", ""),
            "Fonte": TI.normalizar_fonte(c.get("fonte", "")),
            "Link": c.get("link", ""),
            "Origem": c.get("origem", "manual"),
            "Incluir": c.get("incluir", True),
            "Preço total (R$)": float(c.get("preco_total") or 0.0),
            "Área (m²)": float(c.get("area") or 0.0),
            "Conservação": c.get("conservacao") or estado_default,
            "F. Oferta": float(fat.get("f_oferta") or F.FATOR_OFERTA_PADRAO),
            "F. Localiz.": float(fat.get("f_localizacao") or 1.0),
            "F. Área": float(fat.get("f_area") or 1.0),
            "F. Conserv.": float(fat.get("f_conservacao") or 1.0),
            "F. Padrão": float(fat.get("f_padrao") or 1.0),
            "F. Outros": float(fat.get("f_outros") or 1.0),
        })
    return pd.DataFrame(rows)


def _df_comparaveis_para_lista(df) -> list[dict]:
    """Converte o DataFrame do data_editor em lista de dicts serializável
    (mesma forma usada pelo histórico ao reabrir)."""
    if df is None or not hasattr(df, "to_dict") or len(df) == 0:
        return []
    out = []
    for _, row in df.iterrows():
        descr = str(row.get("Descrição") or "").strip()
        preco = float(row.get("Preço total (R$)") or 0) or 0.0
        area = float(row.get("Área (m²)") or 0) or 0.0
        # Linha "totalmente vazia" — ignora
        if not descr and preco == 0.0 and area == 0.0:
            continue
        out.append({
            "descricao": descr,
            "fonte": str(row.get("Fonte") or ""),
            "link": str(row.get("Link") or ""),
            "origem": str(row.get("Origem") or "manual"),
            "incluir": bool(row.get("Incluir") or False),
            "preco_total": preco,
            "area": area,
            "conservacao": str(row.get("Conservação") or ""),
            "fatores": {
                "f_oferta": float(row.get("F. Oferta") or F.FATOR_OFERTA_PADRAO),
                "f_localizacao": float(row.get("F. Localiz.") or 1.0),
                "f_area": float(row.get("F. Área") or 1.0),
                "f_conservacao": float(row.get("F. Conserv.") or 1.0),
                "f_padrao": float(row.get("F. Padrão") or 1.0),
                "f_outros": float(row.get("F. Outros") or 1.0),
            },
        })
    return out


def _persistir_rascunho() -> None:
    """Grava (ou atualiza) o rascunho no banco. Chamado em qualquer mudança
    de campo (on_change) e em qualquer troca de passo."""
    global edic_id
    # Sem nada preenchido ainda? Não cria rascunho vazio.
    imovel = _construir_imovel()
    if not imovel and not edic_id:
        return

    # Comparáveis: usa o df do passo 4 quando existe (estado atual da tabela);
    # senão, cai no resultado calculado (passo 5) ou em vazio.
    comparaveis_atual = _df_comparaveis_para_lista(st.session_state.get("_df_comparaveis"))
    if not comparaveis_atual:
        comparaveis_atual = (st.session_state.get("ultimo_resultado") or {}).get("comparaveis") or []

    dados_rasc = {
        "tipo_imovel": tipo_key,
        "tipo_rotulo": tipo_def["rotulo"],
        "imovel": imovel,
        "imovel_detalhado": _imovel_detalhado(imovel),
        "comparaveis": comparaveis_atual,
        "resultado": (st.session_state.get("ultimo_resultado") or {}).get("resultado") or {},
        "textos_ia": (st.session_state.get("ultimo_resultado") or {}).get("textos_ia") or {},
        "fotos_imovel": (st.session_state.get("ultimo_resultado") or {}).get("fotos_imovel") or [],
    }
    try:
        novo_id = db.salvar_rascunho(dados_rasc, avaliacao_id=edic_id,
                                      passo_atual=WZ.passo_atual())
    except Exception as e:
        # Não bloqueia a digitação se o banco falhar momentaneamente.
        st.session_state["_rascunho_erro"] = str(e)[:200]
        return
    st.session_state["edicao_id"] = novo_id
    st.session_state["rascunho_salvo_em"] = datetime.now().strftime("%H:%M")
    st.session_state.pop("_rascunho_erro", None)
    # Coloca o id na URL — sobrevive a reload e perda de session_state no Cloud.
    try:
        if st.query_params.get("r") != str(novo_id):
            st.query_params["r"] = str(novo_id)
    except Exception:
        pass
    edic_id = novo_id


def _on_change_field(wkey: str) -> None:
    """Callback de qualquer widget de form: salva no shadow e persiste o
    rascunho no Supabase imediatamente. Garante que cada mudança que dispara
    um rerun é guardada — não dependemos de session_state em memória."""
    if wkey in st.session_state:
        st.session_state[f"_p_{wkey}"] = st.session_state[wkey]
    _persistir_rascunho()


# ============================================================================
# STEPPER + estado base para validação
# ============================================================================
imovel_atual = _construir_imovel()
# `comparaveis_atual` só fica disponível depois que o passo 4 foi visitado e
# o usuário clicou "Calcular" — antes disso a validação do passo 4 olha as
# linhas da tabela em tempo real (feita no próprio passo, não no stepper).
dados_para_validar = {
    "tipo_imovel": tipo_key, "imovel": imovel_atual,
    "comparaveis": (st.session_state.get("ultimo_resultado") or {}).get("comparaveis") or [],
}
WZ.render_stepper(dados_para_validar)

passo = WZ.passo_atual()

# Detecta entrada no passo 4 (vindo de outro passo) para descartar o estado
# interno do st.data_editor (deltas acumulados) e forçá-lo a re-renderizar
# usando o df_base atual (que vem de `_df_comparaveis`). Sem isso, as edições
# anteriores são "duplicadas" como deltas em cima do df_base atualizado.
_ultimo_passo = st.session_state.get("_ultimo_passo_render")
if passo == 4 and _ultimo_passo != 4:
    st.session_state["_p4_session_id"] = st.session_state.get("_p4_session_id", 0) + 1
st.session_state["_ultimo_passo_render"] = passo


# ============================================================================
# PASSO 1 · Identificação (solicitante + finalidade + localização)
# ============================================================================
def render_passo_1():
    st.subheader("Passo 1 · Identificação")
    st.caption("Quem está pedindo, para quê, e onde fica o imóvel.")

    # Tipo de imóvel
    idx = tipo_keys.index(tipo_key) if tipo_key in tipo_keys else 0
    novo_label = st.selectbox("Tipo de imóvel", tipo_labels, index=idx, key="tipo_imovel_label")
    novo_tipo = tipo_keys[tipo_labels.index(novo_label)]
    if novo_tipo != tipo_key:
        st.session_state["tipo_imovel_sel"] = novo_tipo
        st.rerun()

    # Identificação
    st.markdown("##### Identificação")
    c1, c2 = st.columns(2)
    campos_ident = TI.GRUPO_IDENTIFICACAO["campos"]
    for i, campo in enumerate(campos_ident):
        with (c1 if i % 2 == 0 else c2):
            _render_campo(campo, "f_ident")

    # Localização — fluxo guiado pelo CEP
    st.markdown("##### Localização")
    st.caption("Comece pelo CEP. O endereço, bairro e cidade vêm automaticamente; "
               "o número você digita.")
    campos_loc = {c["key"]: c for c in TI.GRUPO_LOCALIZACAO["campos"]}

    _render_busca_cep(campos_loc["cep"])

    c1, c2 = st.columns([3, 1])
    with c1:
        _render_campo(campos_loc["endereco"], "f_ident")
    with c2:
        _render_campo(campos_loc["numero"], "f_ident")

    c1, c2 = st.columns(2)
    with c1:
        _render_campo(campos_loc["bairro"], "f_ident")
    with c2:
        _render_campo(campos_loc["cidade_uf"], "f_ident")

    # Coordenadas (preenchidas automaticamente quando o endereço estiver completo)
    _render_campo(campos_loc["geo"], "f_ident")
    prec = st.session_state.get("_geo_precisao")
    if prec and prec != "preciso":
        st.caption(f"ℹ️ {GEO.PRECISAO_LABEL.get(prec, '')}")

    _render_campo(campos_loc["infraestrutura"], "f_ident")

    # Dispara auto-preenchimento de lat/lng se todos os campos do endereço foram preenchidos.
    _autopreencher_geo()


# ============================================================================
# PASSO 2 · Documentos & fotos
# ============================================================================
def render_passo_2():
    st.subheader("Passo 2 · Documentos & fotos")
    st.caption(
        "Suba **matrícula** e **IPTU** para a IA autopreencher os passos 1 e 3, "
        "e adicione as **fotos** do imóvel que entrarão no PTAM e na apresentação."
    )

    _ia_status = IA.status()
    st.markdown("##### 📄 Matrícula / IPTU (OCR por IA)")
    if not _ia_status["configurada"]:
        st.info(
            "IA não configurada. Gere uma chave grátis do Gemini em "
            "https://aistudio.google.com/app/apikey e cole em "
            "`.streamlit/secrets.toml`, seção `[ia]` (veja `secrets.toml.example`)."
        )
    else:
        st.caption(f"Provedor: **{_ia_status['provedor']}** ({_ia_status['modelo']}).")
        doc = st.file_uploader("Documento (JPG, PNG ou PDF)",
                               type=["jpg", "jpeg", "png", "pdf"], key="ocr_doc")
        if doc is not None and st.button("🔎 Extrair dados do documento", key="btn_ocr"):
            mime = doc.type or ("application/pdf"
                                if doc.name.lower().endswith(".pdf") else "image/jpeg")
            with st.spinner("Lendo o documento com IA..."):
                resp = IA.ocr_documento(doc.getvalue(), mime)
            if not resp.ok:
                st.error(resp.erro)
            elif resp.campos:
                preenche = {k: v for k, v in resp.campos.items() if v}
                st.session_state["ocr_sugestoes"] = preenche
                st.success(
                    f"{len(preenche)} campo(s) extraído(s). **Revise as sugestões abaixo.**"
                )
                st.rerun()
            else:
                st.warning("Não consegui estruturar os campos. Texto lido:")
                st.code(resp.texto)

    _render_sugestoes_ocr()

    st.divider()
    st.markdown("##### 📷 Fotos do imóvel")
    st.session_state.setdefault("fotos_imovel", [])
    up_fotos = st.file_uploader(
        "Adicionar fotos (JPG/PNG)", type=["jpg", "jpeg", "png"],
        accept_multiple_files=True, key="fotos_uploader",
    )
    if up_fotos:
        nomes = {f["nome"] for f in st.session_state["fotos_imovel"]}
        novas = 0
        for f in up_fotos:
            if f.name not in nomes:
                st.session_state["fotos_imovel"].append({"nome": f.name, "bytes": f.getvalue()})
                nomes.add(f.name)
                novas += 1
        if novas:
            st.success(f"{novas} foto(s) adicionada(s).")

    fotos = st.session_state["fotos_imovel"]
    st.caption(f"📷 {len(fotos)} foto(s) carregada(s). Elas entram no PTAM e na apresentação.")
    if fotos:
        cols = st.columns(4)
        for i, foto in enumerate(list(fotos)):
            with cols[i % 4]:
                st.image(foto["bytes"], caption=foto["nome"][:20], use_container_width=True)
                if st.button("🗑️ Remover", key=f"rmfoto_{i}"):
                    st.session_state["fotos_imovel"].pop(i)
                    st.rerun()


# ============================================================================
# PASSO 3 · Características do imóvel (form dinâmico do tipo)
# ============================================================================
def render_passo_3():
    st.subheader(f"Passo 3 · Características — {tipo_def['icone']} {tipo_def['rotulo']}")
    st.caption("Dados físicos do imóvel. Quanto mais completo, melhor o grau de fundamentação.")
    # Mostra todos os grupos que NÃO sejam Identificação/Localização (já no passo 1).
    for grupo in tipo_def["grupos"]:
        t = grupo["titulo"].lower()
        if t.startswith("identifi") or t.startswith("localiza"):
            continue
        st.markdown(f"##### {grupo['titulo']}")
        c1, c2 = st.columns(2)
        for i, campo in enumerate(grupo["campos"]):
            with (c1 if i % 2 == 0 else c2):
                _render_campo(campo, f"f_{tipo_key}")


# ============================================================================
# PASSO 4 · Comparáveis (IA / import / manual) + fundamentação qualitativa
# ============================================================================
def _coleta_para_linha(c: dict, estado_avaliando: str, incluir: bool = True) -> dict:
    return {
        "Descrição": c.get("descricao", ""), "Fonte": TI.normalizar_fonte(c.get("fonte", "")),
        "Link": c.get("link", ""),
        "Origem": "automatica", "Incluir": incluir,
        "Preço total (R$)": c.get("preco_total", 0.0), "Área (m²)": c.get("area", 0.0),
        "Conservação": c.get("conservacao") or estado_avaliando,
        "F. Oferta": F.FATOR_OFERTA_PADRAO, "F. Localiz.": 1.0, "F. Área": 1.0,
        "F. Conserv.": 1.0, "F. Padrão": 1.0, "F. Outros": 1.0,
    }


def render_passo_4():
    imovel = _construir_imovel()
    area_key = tipo_def["area_base_key"]
    area_avaliando = float(imovel.get(area_key) or 0)
    tem_conservacao = any(
        campo["key"] == "conservacao"
        for grupo in tipo_def["grupos"] for campo in grupo["campos"]
    )
    estado_avaliando = imovel.get("conservacao") or "Regular"

    st.subheader("Passo 4 · Comparáveis (pesquisa de mercado)")
    st.caption(
        "Três formas de montar a pesquisa, combináveis (modo misto): "
        "**1) IA pesquisa** anúncios na web · **2) você digita** manualmente · "
        "**3) importa** de CSV/texto. Marque **Incluir** para usar no cálculo. "
        f"Fator Oferta padrão = {F.FATOR_OFERTA_PADRAO}; demais fatores: "
        ">1 quando o comparável é inferior ao avaliando."
    )
    if area_avaliando <= 0:
        st.warning(
            f"⚠️ A **área base** ({area_key}) ainda não foi informada no passo 3. "
            "O cálculo automático do **F. Área** vai usar 1,00 até você preencher."
        )

    # Cálculo automático dos fatores Área e Conservação
    auto_fatores = st.checkbox(
        "🔧 Calcular **F. Área** e **F. Conservação** automaticamente (recomendado)",
        value=True, key="auto_fatores_chk",
        help="F. Área pela razão de áreas com expoente; F. Conservação por Ross-Heidecke. "
             "Desligue para informar esses fatores manualmente na tabela.",
    )
    expoente_area = F.EXPOENTE_AREA_PADRAO
    if auto_fatores:
        cexp, cinfo = st.columns([1, 2])
        expoente_area = cexp.number_input(
            "Expoente do fator Área", min_value=0.0, max_value=0.50,
            value=F.EXPOENTE_AREA_PADRAO, step=0.01,
            help="Típico 0,10–0,25 conforme zona/uso.",
            key="expoente_area_inp",
        )
        if tem_conservacao:
            cinfo.caption(f"Estado de conservação do avaliando: **{estado_avaliando}**. "
                          "Informe o estado de cada comparável na coluna **Conservação**.")
        else:
            cinfo.caption("Este tipo de imóvel não tem construção — F. Conservação = 1,00.")

    _ia_status = IA.status()

    def _adicionar_importados(comparaveis: list[dict], avisos: list[str]):
        for a in avisos:
            st.warning(a)
        if comparaveis:
            novas = [_coleta_para_linha(c, estado_avaliando) for c in comparaveis]
            st.session_state.setdefault("comparaveis_importados", []).extend(novas)
            st.session_state["import_rev"] = st.session_state.get("import_rev", 0) + 1
            st.success(f"{len(novas)} comparável(is) importado(s). "
                       "Revise e marque **Incluir** na tabela abaixo.")
            st.rerun()

    # Busca por IA
    with st.expander("🤖 Buscar comparáveis com IA (pesquisa na web)", expanded=False):
        if not _ia_status["configurada"]:
            st.info("IA não configurada — veja o passo 2.")
        else:
            st.caption(
                "A IA pesquisa anúncios reais semelhantes ao imóvel e os traz como "
                "**origem 'automatica'**, **sem marcar Incluir**: você confere cada "
                "anúncio pelo link e decide o que entra no cálculo."
            )
            _sem_local = not (imovel.get("cidade_uf") or imovel.get("bairro") or imovel.get("endereco"))
            if _sem_local:
                st.warning("Informe ao menos a **cidade/UF** ou o **bairro** (passo 1).")
            if st.button("🔎 Pesquisar comparáveis com IA",
                         key="btn_ia_busca", disabled=_sem_local):
                with st.spinner("Pesquisando anúncios na web com IA..."):
                    resp = IA.buscar_comparaveis(imovel, tipo_def.get("rotulo", ""))
                if not resp.ok:
                    st.error(resp.erro)
                else:
                    novas = [_coleta_para_linha(c, estado_avaliando, incluir=False)
                             for c in resp.comparaveis]
                    st.session_state.setdefault("comparaveis_importados", []).extend(novas)
                    st.session_state["import_rev"] = st.session_state.get("import_rev", 0) + 1
                    st.success(f"{len(novas)} comparável(is) encontrado(s) pela IA. "
                               "Revise pelos links e marque **Incluir**.")
                    st.rerun()
            st.caption("⚠️ Anúncios podem estar **desatualizados ou imprecisos** — "
                       "**sempre confira pelo link** antes de usar no parecer.")

    # Import CSV / texto
    with st.expander("📥 Importar comparáveis (CSV ou colar texto)"):
        st.caption("Importação local — você controla a fonte.")
        aba_csv, aba_texto = st.tabs(["📄 CSV", "📝 Colar texto"])
        with aba_csv:
            st.caption("Colunas: descricao, fonte, preco (ou valor), area (ou m2), conservacao.")
            up = st.file_uploader("Arquivo CSV", type=["csv"], key="csv_comparaveis")
            if up is not None and st.button("Importar CSV", key="btn_csv"):
                _adicionar_importados(*CO.importar_csv(up.getvalue()))
        with aba_texto:
            st.caption("Uma linha por imóvel, contendo preço (R$ ...) e área (... m²).")
            txt = st.text_area("Lista de imóveis", height=140, key="txt_comparaveis",
                               placeholder="Apto 2 quartos, Centro - R$ 420.000 - 65 m²")
            if st.button("Importar texto", key="btn_txt"):
                _adicionar_importados(*CO.importar_texto(txt))

        if st.session_state.get("comparaveis_importados"):
            n_imp = len(st.session_state["comparaveis_importados"])
            if st.button(f"🗑️ Limpar {n_imp} importado(s)", key="btn_limpar_imp"):
                st.session_state.pop("comparaveis_importados", None)
                st.session_state["import_rev"] = st.session_state.get("import_rev", 0) + 1
                st.rerun()

    # Tabela de comparáveis — origem do df_base, em ordem de prioridade:
    #   1) `_df_comparaveis` (a fonte da verdade entre runs/passos)
    #   2) hidratação do histórico (`edic.comparaveis`), uma vez
    #   3) df padrão de 3 linhas vazias
    df_persistido = st.session_state.get("_df_comparaveis")
    if isinstance(df_persistido, pd.DataFrame) and not df_persistido.empty:
        df_base = df_persistido.copy()
    elif edic and edic.get("comparaveis") and "_comp_base_carregado" not in st.session_state:
        base_rows = []
        for c in edic["comparaveis"]:
            fat = c.get("fatores", {})
            base_rows.append({
                "Descrição": c.get("descricao", ""),
                "Fonte": TI.normalizar_fonte(c.get("fonte", "")),
                "Link": c.get("link", ""),
                "Origem": c.get("origem", "manual"), "Incluir": c.get("incluir", True),
                "Preço total (R$)": c.get("preco_total", 0.0), "Área (m²)": c.get("area", 0.0),
                "Conservação": c.get("conservacao") or estado_avaliando,
                "F. Oferta": fat.get("f_oferta", F.FATOR_OFERTA_PADRAO),
                "F. Localiz.": fat.get("f_localizacao", 1.0), "F. Área": fat.get("f_area", 1.0),
                "F. Conserv.": fat.get("f_conservacao", 1.0),
                "F. Padrão": fat.get("f_padrao", 1.0), "F. Outros": fat.get("f_outros", 1.0),
            })
        df_base = pd.DataFrame(base_rows)
        st.session_state["_comp_base_carregado"] = True
    else:
        df_base = pd.DataFrame([{
            "Descrição": "", "Fonte": "", "Link": "", "Origem": "manual", "Incluir": True,
            "Preço total (R$)": 0.0, "Área (m²)": 0.0, "Conservação": estado_avaliando,
            "F. Oferta": F.FATOR_OFERTA_PADRAO,
            "F. Localiz.": 1.0, "F. Área": 1.0, "F. Conserv.": 1.0,
            "F. Padrão": 1.0, "F. Outros": 1.0,
        } for _ in range(3)])

    # Importações pendentes (IA/CSV/texto) são absorvidas no df_base e a
    # fila é limpa — assim não viram duplicatas a cada rerun.
    importados = st.session_state.get("comparaveis_importados", [])
    if importados:
        df_base = pd.concat([df_base, pd.DataFrame(importados)], ignore_index=True)
        st.session_state.pop("comparaveis_importados", None)
        st.session_state["_df_comparaveis"] = df_base  # já reflete a soma

    cols_ocultas = ["F. Área", "F. Conserv."] if auto_fatores else []
    if not tem_conservacao:
        cols_ocultas.append("Conservação")

    col_config = {
        "Fonte": st.column_config.SelectboxColumn(options=TI.FONTE_COMPARAVEL),
        "Link": st.column_config.LinkColumn("Link", display_text="abrir 🔗"),
        "Origem": st.column_config.SelectboxColumn(options=["manual", "automatica"]),
        "Incluir": st.column_config.CheckboxColumn(),
        "Preço total (R$)": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
        "Área (m²)": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
        "Conservação": st.column_config.SelectboxColumn(options=TI.ESTADO_CONSERVACAO),
        **{c: st.column_config.NumberColumn(format="%.3f", min_value=0.0)
           for c in ["F. Oferta", "F. Localiz.", "F. Área", "F. Conserv.", "F. Padrão", "F. Outros"]},
    }

    # A key inclui _p4_session_id (incrementado ao entrar no passo 4) e
    # import_rev (incrementado em cada nova importação). Ambos forçam o
    # data_editor a descartar deltas internos antigos e re-renderizar do
    # df_base novo — evita duplicação de linhas em cima das edições passadas.
    _p4sid = st.session_state.get("_p4_session_id", 0)
    _imprev = st.session_state.get("import_rev", 0)
    df_edit = st.data_editor(
        df_base, num_rows="dynamic", use_container_width=True,
        key=f"editor_comparaveis_s{_p4sid}_r{_imprev}",
        column_order=[c for c in df_base.columns if c not in cols_ocultas],
        column_config=col_config,
    )

    # Prévia "Fatores aplicados" (padrões em cinza/itálico)
    _FATOR_DEFAULTS = {
        "F. Oferta": F.FATOR_OFERTA_PADRAO, "F. Localiz.": 1.0,
        "F. Área": 1.0, "F. Conserv.": 1.0, "F. Padrão": 1.0, "F. Outros": 1.0,
    }

    def _vazio(v) -> bool:
        return v is None or (isinstance(v, float) and math.isnan(v))

    _fator_cols_prev = [c for c in _FATOR_DEFAULTS if c not in cols_ocultas]
    _idx_prev = [
        i for i in range(len(df_edit))
        if not _vazio(df_edit["Preço total (R$)"].iloc[i])
        or not _vazio(df_edit["Área (m²)"].iloc[i])
        or str(df_edit["Descrição"].iloc[i] or "").strip()
    ]
    if _fator_cols_prev and _idx_prev:
        prev_data, prev_mask = {}, {}
        prev_data["Comparável"] = [
            (str(df_edit["Descrição"].iloc[i] or "").strip() or f"Linha {i + 1}")
            for i in _idx_prev
        ]
        prev_mask["Comparável"] = [False] * len(_idx_prev)
        for col in _fator_cols_prev:
            vals, mask = [], []
            for i in _idx_prev:
                v = df_edit[col].iloc[i] if col in df_edit.columns else None
                if _vazio(v):
                    vals.append(_FATOR_DEFAULTS[col]); mask.append(True)
                else:
                    vals.append(float(v)); mask.append(False)
            prev_data[col], prev_mask[col] = vals, mask
        prev_df = pd.DataFrame(prev_data)
        mask_df = pd.DataFrame(prev_mask).replace(
            {True: "color:#9aa0a6;font-style:italic", False: ""}
        )
        styler = (prev_df.style
                  .apply(lambda _: mask_df, axis=None)
                  .format({c: "{:.3f}" for c in _fator_cols_prev}))
        st.caption("🔎 **Fatores aplicados** — em cinza/itálico estão valores padrão.")
        st.dataframe(styler, use_container_width=True, hide_index=True)

    # Fundamentação NBR — itens qualitativos
    with st.expander("⚖️ Fundamentação — itens qualitativos (NBR 14653-2)"):
        st.caption("Itens 1 e 3 dependem da documentação disponível.")
        GRAUS = {"Grau III": "III", "Grau II": "II", "Grau I": "I"}
        gc1, gc2 = st.columns(2)
        gc1.selectbox("1. Caracterização do imóvel", list(GRAUS), index=1,
                      key="grau_caract_lbl",
                      help="III: completa; II: p/ fatores usados; I: paradigma.")
        gc2.selectbox("3. Identificação dos dados de mercado", list(GRAUS), index=1,
                      key="grau_ident_lbl",
                      help="III: c/ foto e características; II: todas; I: só dos fatores.")

    # Salva o df no session_state para o passo 5 ler na hora de calcular.
    st.session_state["_df_comparaveis"] = df_edit
    st.session_state["_auto_fatores"] = auto_fatores
    st.session_state["_expoente_area"] = expoente_area
    st.session_state["_tem_conservacao"] = tem_conservacao
    st.session_state["_estado_avaliando"] = estado_avaliando
    st.session_state["_area_avaliando"] = area_avaliando

    # Persiste o rascunho com o df atualizado dos comparáveis. O Streamlit
    # Cloud pode descartar o session_state — gravar a cada rerun do passo 4
    # garante que o banco reflete sempre o estado atual da tabela.
    _persistir_rascunho()


# ============================================================================
# PASSO 5 · Cálculo & entrega
# ============================================================================
def _num(valor, default: float) -> float:
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def render_passo_5():
    imovel = _construir_imovel()
    st.subheader("Passo 5 · Cálculo & entrega")

    # Validação completa de obrigatórios antes de calcular
    dados_check = {
        "tipo_imovel": tipo_key, "imovel": imovel,
        "comparaveis": [],  # validação do passo 4 será feita logo abaixo
    }
    pendencias = WZ.validar_completo(dados_check)
    # Também valida comparáveis a partir do df do passo 4. Se o session_state
    # foi descartado, reconstrói o df a partir do rascunho persistido no banco.
    df_edit = st.session_state.get("_df_comparaveis")
    if (df_edit is None or (hasattr(df_edit, "empty") and df_edit.empty)) \
            and edic and edic.get("comparaveis"):
        df_edit = _lista_para_df_comparaveis(
            edic["comparaveis"], imovel.get("conservacao") or "Regular"
        )
        st.session_state["_df_comparaveis"] = df_edit

    # Contadores para mensagem específica e debug visível
    n_total = 0
    n_com_preco = 0
    n_com_area = 0
    n_incluir_marcado = 0
    comp_validos = 0
    if df_edit is not None and hasattr(df_edit, "iterrows"):
        for _, row in df_edit.iterrows():
            preco = _num(row.get("Preço total (R$)"), 0.0)
            area = _num(row.get("Área (m²)"), 0.0)
            incluir = bool(row.get("Incluir"))
            if preco > 0 or area > 0 or str(row.get("Descrição") or "").strip():
                n_total += 1
            if preco > 0:
                n_com_preco += 1
            if area > 0:
                n_com_area += 1
            if incluir:
                n_incluir_marcado += 1
            if incluir and preco > 0 and area > 0:
                comp_validos += 1

    if comp_validos == 0:
        # Mensagem específica de acordo com o motivo
        if n_total == 0:
            msg = "Nenhum comparável digitado ainda. Vá no passo 4 e preencha pelo menos 1."
        elif n_com_preco == 0:
            msg = f"Você tem {n_total} comparável(is), mas nenhum com **Preço total** preenchido."
        elif n_com_area == 0:
            msg = f"Você tem {n_total} comparável(is), mas nenhum com **Área** preenchida."
        elif n_incluir_marcado == 0:
            msg = (f"Você tem {n_total} comparável(is) preenchidos, mas nenhum com a "
                   f"caixinha **Incluir** marcada no passo 4. Marque ao menos 1.")
        else:
            msg = ("Ao menos 1 comparável precisa ter **Incluir marcado E** preço E área "
                   "preenchidos simultaneamente.")
        pendencias.setdefault(4, []).append(msg)

    if pendencias:
        st.warning("Antes de finalizar, ainda faltam preencher:")
        for p_id, faltas in sorted(pendencias.items()):
            passo_def = next(p for p in WZ.PASSOS if p["id"] == p_id)
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{passo_def['icone']} Passo {p_id} — {passo_def['titulo']}:** "
                        + ", ".join(faltas))
            if c2.button(f"→ Ir ao passo {p_id}", key=f"goto_{p_id}",
                         use_container_width=True):
                WZ.ir_para(p_id)

        # Debug visível quando há pendência de comparáveis — mostra exatamente
        # o que o sistema está lendo da tabela do passo 4, para o usuário ver
        # por que a validação está falhando.
        if 4 in pendencias:
            with st.expander("🔍 O que o sistema enxerga na tabela (debug)", expanded=True):
                st.caption(
                    f"Linhas com algum dado: **{n_total}** · com Preço: **{n_com_preco}** · "
                    f"com Área: **{n_com_area}** · com 'Incluir' marcado: **{n_incluir_marcado}**"
                )
                if df_edit is not None and hasattr(df_edit, "iterrows") and n_total > 0:
                    _cols_show = [c for c in ["Descrição", "Incluir",
                                              "Preço total (R$)", "Área (m²)", "Fonte"]
                                  if c in df_edit.columns]
                    _df_show = df_edit[_cols_show].copy()
                    # Só mostra linhas com algum dado preenchido
                    _df_show = _df_show[
                        (_df_show.get("Descrição", "").astype(str).str.strip() != "")
                        | (_df_show.get("Preço total (R$)", 0).fillna(0) > 0)
                        | (_df_show.get("Área (m²)", 0).fillna(0) > 0)
                    ]
                    if not _df_show.empty:
                        st.dataframe(_df_show, use_container_width=True, hide_index=True)
                else:
                    st.info("A tabela de comparáveis está vazia no momento (do ponto de "
                            "vista do servidor). Vá no passo 4, preencha pelo menos uma "
                            "linha (Descrição + Preço + Área) e marque o 'Incluir'.")

    pode_calcular = not pendencias
    if st.button("🧮 Calcular avaliação", type="primary", disabled=not pode_calcular):
        # Monta comparáveis a partir do df do passo 4
        auto_fatores = st.session_state.get("_auto_fatores", True)
        expoente_area = st.session_state.get("_expoente_area", F.EXPOENTE_AREA_PADRAO)
        tem_conservacao = st.session_state.get("_tem_conservacao", True)
        estado_avaliando = st.session_state.get("_estado_avaliando", "Regular")
        area_avaliando = st.session_state.get("_area_avaliando", 0.0)

        comparaveis = []
        for _, row in df_edit.iterrows():
            preco_cp = _num(row.get("Preço total (R$)"), 0.0)
            area_cp = _num(row.get("Área (m²)"), 0.0)
            if not (preco_cp or area_cp):
                continue
            estado_cp = str(row.get("Conservação") or estado_avaliando)
            if auto_fatores:
                f_area = F.fator_area(area_avaliando, area_cp, expoente_area)
                f_conserv = (F.fator_conservacao(estado_avaliando, estado_cp)
                             if tem_conservacao else 1.0)
            else:
                f_area = _num(row.get("F. Área"), 1.0)
                f_conserv = _num(row.get("F. Conserv."), 1.0)
            comparaveis.append(Comparavel(
                descricao=str(row.get("Descrição") or ""),
                fonte=str(row.get("Fonte") or ""),
                link=str(row.get("Link") or ""),
                origem=str(row.get("Origem") or "manual"),
                incluir=bool(row.get("Incluir")),
                preco_total=preco_cp,
                area=area_cp,
                conservacao=estado_cp,
                fatores={
                    "f_oferta": _num(row.get("F. Oferta"), F.FATOR_OFERTA_PADRAO),
                    "f_localizacao": _num(row.get("F. Localiz."), 1.0),
                    "f_area": round(f_area, 4),
                    "f_conservacao": round(f_conserv, 4),
                    "f_padrao": _num(row.get("F. Padrão"), 1.0),
                    "f_outros": _num(row.get("F. Outros"), 1.0),
                },
            ))

        GRAUS = {"Grau III": "III", "Grau II": "II", "Grau I": "I"}
        grau_caract = GRAUS.get(st.session_state.get("grau_caract_lbl", "Grau II"), "II")
        grau_ident = GRAUS.get(st.session_state.get("grau_ident_lbl", "Grau II"), "II")

        resultado = calcular(comparaveis, area_avaliando,
                             grau_caracterizacao=grau_caract,
                             grau_identificacao=grau_ident)
        dados = {
            "tipo_imovel": tipo_key, "tipo_rotulo": tipo_def["rotulo"],
            "imovel": imovel, "imovel_detalhado": _imovel_detalhado(imovel),
            "comparaveis": [c.__dict__ for c in resultado.comparaveis],
            "resultado": {
                "valor_unitario_medio": resultado.valor_unitario_medio,
                "valor_total": resultado.valor_total,
                "valor_min_arbitrio": resultado.valor_min_arbitrio,
                "valor_max_arbitrio": resultado.valor_max_arbitrio,
                "n_comparaveis_usados": resultado.n_comparaveis_usados,
                "coef_variacao": resultado.coef_variacao,
                "grau_fundamentacao": resultado.grau_fundamentacao,
                "grau_pontos": resultado.grau_pontos,
                "graus_itens": resultado.graus_itens,
                "avisos": resultado.avisos,
            },
        }
        st.session_state["ultimo_resultado"] = dados
        st.session_state["ultimo_resultado_obj"] = resultado

    # Exibição do resultado
    dados = st.session_state.get("ultimo_resultado")
    resultado = st.session_state.get("ultimo_resultado_obj")
    if not (dados and resultado):
        return

    st.divider()
    st.subheader("📊 Resultado")
    r = dados["resultado"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Valor de mercado", formatar_brl(r["valor_total"]))
    c2.metric("Valor unitário", f"{formatar_brl(r['valor_unitario_medio'])}/m²")
    c3.metric("Grau de fundamentação", r["grau_fundamentacao"])
    pontos_txt = f"  ·  {r['grau_pontos']}/12 pontos" if r.get("grau_pontos") else ""
    st.caption(
        f"Faixa (campo de arbítrio ±15%): {formatar_brl(r['valor_min_arbitrio'])} a "
        f"{formatar_brl(r['valor_max_arbitrio'])}  ·  "
        f"{r['n_comparaveis_usados']} comparáveis usados{pontos_txt}  ·  "
        f"CV {r['coef_variacao']:.0f}% (informativo)"
    )
    if r.get("graus_itens"):
        rotulos = {"1_caracterizacao": "1·Caracterização", "2_quantidade": "2·Qtd. dados",
                   "3_identificacao": "3·Identif. dados", "4_conjunto_fatores": "4·Conjunto fatores"}
        st.caption("Itens NBR: " + "  ·  ".join(
            f"{rotulos.get(k, k)}: **{v}**" for k, v in r["graus_itens"].items()))
    for aviso in r["avisos"]:
        st.warning(aviso)

    tab = pd.DataFrame([{
        "Comparável": c["descricao"] or c["fonte"] or "—",
        "R$/m²": round(c["valor_unitario"], 2),
        "Fator total": round(c["fator_total"], 3),
        "Homogeneizado R$/m²": round(c["valor_homogeneizado"], 2),
        "Usado": "✅" if c.get("valido") and c.get("incluir") else "—",
        "Obs.": c.get("motivo_descarte", ""),
    } for c in dados["comparaveis"]])
    st.dataframe(tab, use_container_width=True, hide_index=True)

    # Apoio de IA pós-cálculo
    st.divider()
    st.subheader("🤖 Apoio de IA")
    _ia_status = IA.status()
    if not _ia_status["configurada"]:
        st.info("IA não configurada — veja o passo 2.")
    else:
        dados.setdefault("textos_ia", {})
        ia_tab1, ia_tab2 = st.tabs(["🔍 Analisar comparáveis", "✍️ Redigir seções do PTAM"])
        with ia_tab1:
            if st.button("Analisar pesquisa de mercado", key="btn_ia_analise"):
                with st.spinner("Analisando com IA..."):
                    resp = IA.analisar_comparaveis(dados)
                if resp.ok:
                    st.session_state["ia_analise"] = resp.texto
                else:
                    st.error(resp.erro)
            if st.session_state.get("ia_analise"):
                with st.container(height=320, border=True):
                    st.markdown(st.session_state["ia_analise"])
                st.caption("Sugestão da IA — revise criticamente antes de usar.")
        with ia_tab2:
            sec_label = st.selectbox("Seção a redigir", list(IA.SECOES.values()),
                                     key="ia_sec_sel")
            sec_key = next(k for k, v in IA.SECOES.items() if v == sec_label)
            if st.button("✨ Gerar texto da seção", key="btn_ia_secao"):
                with st.spinner("Redigindo com IA..."):
                    resp = IA.redigir_secao(sec_key, dados)
                if resp.ok:
                    st.session_state.setdefault("ia_textos", {})[sec_key] = resp.texto
                else:
                    st.error(resp.erro)
            texto_atual = (st.session_state.get("ia_textos", {}).get(sec_key)
                           or dados["textos_ia"].get(sec_key, ""))
            editado = st.text_area("Texto gerado (edite à vontade)", value=texto_atual,
                                   height=180, key=f"ia_ta_{sec_key}")
            usar = st.checkbox("Incluir este texto no PDF do PTAM",
                               value=bool(dados["textos_ia"].get(sec_key)),
                               key=f"ia_use_{sec_key}")
            if usar and editado.strip():
                dados["textos_ia"][sec_key] = editado.strip()
            else:
                dados["textos_ia"].pop(sec_key, None)
            if dados["textos_ia"]:
                st.caption("No PDF: " + ", ".join(IA.SECOES[k] for k in dados["textos_ia"]))

    # Salvar + PDFs
    fotos = st.session_state.get("fotos_imovel", [])
    st.divider()
    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("💾 Salvar no histórico", type="primary"):
            novo_id = db.salvar(dados, avaliacao_id=st.session_state.get("edicao_id"),
                                status=db.STATUS_CONCLUIDO, passo_atual=5)
            dados["fotos_imovel"] = AN.salvar_fotos(novo_id, fotos)
            db.salvar(dados, avaliacao_id=novo_id,
                      status=db.STATUS_CONCLUIDO, passo_atual=5)
            st.session_state["edicao_id"] = novo_id
            st.success(f"Avaliação salva (#{novo_id}).")
    with a2:
        st.download_button("📄 PDF — PTAM completo",
                           data=PDFGEN.gerar_ptam(dados, fotos=fotos),
                           file_name="PTAM.pdf", mime="application/pdf")
    with a3:
        st.download_button("🎯 PDF — Apresentação",
                           data=PDFGEN.gerar_apresentacao(dados, fotos=fotos),
                           file_name="Apresentacao.pdf", mime="application/pdf")


# ============================================================================
# DISPATCH
# ============================================================================
RENDERS = {1: render_passo_1, 2: render_passo_2, 3: render_passo_3,
           4: render_passo_4, 5: render_passo_5}
RENDERS[passo]()

# Barra de navegação inferior — salva rascunho ao trocar de passo
WZ.render_nav_inferior(on_avancar=_persistir_rascunho,
                        on_voltar=_persistir_rascunho)

# Sidebar — status do rascunho + ação de limpar
with st.sidebar:
    if st.session_state.get("edicao_id") and st.session_state.get("rascunho_salvo_em"):
        st.caption(f"🟡 Rascunho #{st.session_state['edicao_id']} · "
                   f"salvo {st.session_state['rascunho_salvo_em']}")
    if st.button("💾 Salvar rascunho agora", use_container_width=True):
        _persistir_rascunho()
        st.rerun()
    if st.button("🆕 Limpar / nova avaliação", use_container_width=True):
        st.session_state["_resetar_form"] = True
        st.rerun()
