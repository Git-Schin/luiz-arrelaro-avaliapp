"""
Wizard de Vistoria de Imóvel para Locação.

Três passos:
  1. Identificação  — imóvel, data, partes envolvidas
  2. Cômodos        — cômodo a cômodo; item a item no modo mobile
  3. Fechamento     — medidores, chaves, observações gerais, laudo PDF

Mobile: fluxo item a item dentro de cada cômodo, câmera nativa como
        método principal de foto. Detectado via User-Agent, com toggle
        manual na sidebar para override.
"""
from __future__ import annotations

import streamlit as st
from datetime import date

from config import identidade as ID
from core import cep as CEP
from core import vistoria_db as VDB
from core import vistoria_tipos as VT
from core import vistoria_anexos as VAN
from core import pdf_vistoria as PDFVIST
from core.ui import detectar_mobile

# ── Keys do session_state ─────────────────────────────────────────────────────
_K_DADOS      = "vistoria"
_K_ID         = "vistoria_id"
_K_PASSO      = "vistoria_passo"
_K_COMODO     = "vistoria_comodo_idx"
_K_ITEM       = "vistoria_item_idx"
_K_RESET      = "_resetar_vistoria"
_K_ADICIONANDO = "vistoria_adicionando_comodo"

_RESET_KEYS = [_K_DADOS, _K_ID, _K_PASSO, _K_COMODO, _K_ITEM,
               "vistoria_entrada_dados", _K_ADICIONANDO]

# Opções rápidas de cômodo para o panel de inclusão
_COMODOS_RAPIDOS = [
    ("🛋️", "Sala de Estar"),
    ("🍽️", "Sala de Jantar"),
    ("🍳", "Cozinha"),
    ("🧺", "Área de Serviço"),
    ("🛏️", "Quarto 1"),
    ("🛏️", "Quarto 2"),
    ("🛏️", "Quarto 3"),
    ("🛏️", "Suíte Master"),
    ("🚿", "Banheiro Social"),
    ("🚿", "Banheiro Suíte"),
    ("🚗", "Garagem"),
    ("🌿", "Varanda"),
    ("🌳", "Área Externa"),
    ("💼", "Escritório"),
    ("🚪", "Hall de Entrada"),
    ("🪟", "Corredor"),
    ("📦", "Despensa"),
]

# ── Callbacks on_click (evitam duplo clique) ─────────────────────────────────

def _cb_ir_para(passo: int):
    st.session_state[_K_PASSO] = passo
    st.session_state[_K_COMODO] = None
    st.session_state[_K_ITEM] = None


def _cb_abrir_comodo(ci: int):
    st.session_state[_K_COMODO] = ci
    st.session_state[_K_ITEM] = 0


def _cb_voltar_lista():
    st.session_state[_K_COMODO] = None
    st.session_state[_K_ITEM] = None


def _cb_set_item(ii: int):
    st.session_state[_K_ITEM] = ii


def _cb_concluir_comodo(ci: int):
    comodos = st.session_state.get(_K_DADOS, {}).get("comodos") or []
    if ci < len(comodos):
        comodos[ci]["concluido"] = True
    st.session_state[_K_COMODO] = None
    st.session_state[_K_ITEM] = None


def _cb_desmarcar_comodo(ci: int):
    comodos = st.session_state.get(_K_DADOS, {}).get("comodos") or []
    if ci < len(comodos):
        comodos[ci]["concluido"] = False


def _cb_remover_comodo(ci: int):
    comodos = st.session_state.get(_K_DADOS, {}).get("comodos") or []
    if ci < len(comodos):
        comodos.pop(ci)


def _cb_toggle_adicionando():
    st.session_state[_K_ADICIONANDO] = True


def _cb_fechar_adicionando():
    st.session_state[_K_ADICIONANDO] = False


# ── Reset ─────────────────────────────────────────────────────────────────────
if st.session_state.pop(_K_RESET, False):
    for k in _RESET_KEYS:
        st.session_state.pop(k, None)

# ── Inicializar estado ────────────────────────────────────────────────────────
_perfil = st.session_state.get("perfil") or {}
if _K_DADOS not in st.session_state:
    st.session_state[_K_DADOS] = VT.dados_vistoria_vazio(_perfil)
if _K_PASSO not in st.session_state:
    st.session_state[_K_PASSO] = 1
if _K_COMODO not in st.session_state:
    st.session_state[_K_COMODO] = None
if _K_ITEM not in st.session_state:
    st.session_state[_K_ITEM] = None

_USER_ID  = st.session_state.get("user_id")
_AVALIADOR = _perfil

# ── Detectar mobile ───────────────────────────────────────────────────────────
_mobile_auto = detectar_mobile()


# ── Helpers gerais ────────────────────────────────────────────────────────────

def _dados() -> dict:
    return st.session_state[_K_DADOS]


def _ir_para(passo: int):
    st.session_state[_K_PASSO] = passo
    st.session_state[_K_COMODO] = None
    st.session_state[_K_ITEM] = None


def _salvar_rascunho() -> int:
    vid = st.session_state.get(_K_ID)
    vid = VDB.salvar_rascunho(_dados(), user_id=_USER_ID, vistoria_id=vid)
    st.session_state[_K_ID] = vid
    return vid


def _progresso_comodos() -> tuple[int, int]:
    comodos = _dados().get("comodos") or []
    return sum(1 for c in comodos if c.get("concluido")), len(comodos)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    vid = st.session_state.get(_K_ID)
    if st.button("💾 Salvar rascunho", use_container_width=True):
        try:
            vid = _salvar_rascunho()
            st.toast(f"Rascunho #{vid} salvo!", icon="✅")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
    if vid:
        st.caption(f"🟡 Rascunho #{vid}")
    st.divider()
    conc, tot = _progresso_comodos()
    st.caption(f"Cômodos: {conc}/{tot} vistoriados")
    st.divider()
    # Toggle modo mobile — detectado automaticamente, mas editável
    is_mobile = st.toggle(
        "📱 Modo mobile",
        value=_mobile_auto,
        key="modo_mobile",
        help="Ativado automaticamente em celulares. Liga o fluxo item a item com câmera.",
    )

# ── Título ────────────────────────────────────────────────────────────────────
tipo = _dados().get("tipo", "entrada")
titulo = "🔑 Nova Vistoria de Entrada" if tipo == "entrada" else "🏁 Nova Vistoria de Saída"
st.title(titulo)

# ── Stepper ───────────────────────────────────────────────────────────────────
passo_atual = st.session_state[_K_PASSO]
passos_labels = ["1. Identificação", "2. Cômodos", "3. Fechamento"]
cols_step = st.columns(3)
for i, (col, label) in enumerate(zip(cols_step, passos_labels), start=1):
    with col:
        if i == passo_atual:
            st.button(label, key=f"step_{i}", disabled=True,
                      type="primary", use_container_width=True)
        else:
            st.button(label, key=f"step_{i}", use_container_width=True,
                      on_click=_cb_ir_para, args=(i,))

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 1 — IDENTIFICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _render_passo_1():
    dados = _dados()
    ident = dados.setdefault("identificacao", {})

    st.subheader("Identificação da Vistoria")

    tipo_opcoes = {
        "Vistoria de Entrada (início da locação)": "entrada",
        "Vistoria de Saída (fim da locação)": "saida",
    }
    tipo_label_atual = next(
        (k for k, v in tipo_opcoes.items() if v == dados.get("tipo", "entrada")),
        list(tipo_opcoes.keys())[0],
    )
    tipo_sel = st.radio("Tipo de vistoria", list(tipo_opcoes.keys()),
                        index=list(tipo_opcoes.keys()).index(tipo_label_atual),
                        horizontal=not is_mobile)
    dados["tipo"] = tipo_opcoes[tipo_sel]

    if dados["tipo"] == "saida":
        st.info("ℹ️ Vistoria de saída: estados da entrada aparecem ao lado para comparação.")
        try:
            entradas = VDB.listar_entradas_concluidas(user_id=_USER_ID)
        except Exception:
            entradas = []
        if entradas:
            opcoes_ent = {
                f"#{e['id']} · {e.get('endereco', '')} · {e.get('locatario_nome', '')}": e["id"]
                for e in entradas
            }
            ent_atual_id = dados.get("vistoria_entrada_id")
            ent_atual_label = next(
                (k for k, v in opcoes_ent.items() if v == ent_atual_id), None
            )
            sel_ent = st.selectbox(
                "Vincular à vistoria de entrada",
                ["— não vincular —"] + list(opcoes_ent.keys()),
                index=(list(opcoes_ent.keys()).index(ent_atual_label) + 1)
                      if ent_atual_label else 0,
            )
            if sel_ent == "— não vincular —":
                dados["vistoria_entrada_id"] = None
                st.session_state.pop("vistoria_entrada_dados", None)
            else:
                eid = opcoes_ent[sel_ent]
                dados["vistoria_entrada_id"] = eid
                if st.session_state.get("vistoria_entrada_dados", {}).get("_id") != eid:
                    try:
                        row = VDB.obter(eid, user_id=_USER_ID)
                        if row:
                            ed = dict(row.get("dados") or {})
                            ed["_id"] = eid
                            st.session_state["vistoria_entrada_dados"] = ed
                    except Exception:
                        pass
        else:
            st.warning("Nenhuma vistoria de entrada concluída encontrada.")

    st.divider()

    st.markdown("**Endereço do imóvel**")
    c1, c2 = st.columns([2, 1])
    cep_val = c1.text_input("CEP", value=ident.get("cep", ""),
                             placeholder="00000-000", key="v_cep")
    ident["cep"] = cep_val
    if c2.button("🔍 Buscar CEP", use_container_width=True):
        resultado = CEP.buscar_cep(cep_val)
        if resultado:
            ident["endereco"]  = resultado.get("logradouro", "")
            ident["bairro"]    = resultado.get("bairro", "")
            ident["cidade_uf"] = resultado.get("cidade_uf", "")
            st.toast(f"CEP localizado em {resultado.get('cidade_uf', '')}", icon="📍")
            st.rerun()
        else:
            st.warning("CEP não encontrado. Preencha manualmente.")

    c3, c4 = st.columns([3, 1])
    ident["endereco"] = c3.text_input("Logradouro / Rua",
                                       value=ident.get("endereco", ""), key="v_end")
    ident["numero"]   = c4.text_input("Número", value=ident.get("numero", ""), key="v_num")

    c5, c6 = st.columns(2)
    ident["bairro"]    = c5.text_input("Bairro", value=ident.get("bairro", ""), key="v_bai")
    ident["cidade_uf"] = c6.text_input("Cidade/UF", value=ident.get("cidade_uf", ""),
                                        placeholder="Campinas/SP", key="v_cuf")
    st.divider()

    data_str = ident.get("data_vistoria")
    try:
        data_val = date.fromisoformat(str(data_str)[:10]) if data_str else date.today()
    except Exception:
        data_val = date.today()
    nova_data = st.date_input("📅 Data da vistoria", value=data_val, key="v_data")
    ident["data_vistoria"] = nova_data.isoformat() if nova_data else None

    st.divider()
    st.markdown("**Partes envolvidas**")
    c7, c8 = st.columns(2)
    ident["locatario_nome"] = c7.text_input("Locatário — nome",
                                             value=ident.get("locatario_nome", ""), key="v_loc_n")
    ident["locatario_doc"]  = c8.text_input("Locatário — CPF/RG",
                                             value=ident.get("locatario_doc", ""), key="v_loc_d")
    c9, c10 = st.columns(2)
    ident["proprietario_nome"] = c9.text_input("Proprietário — nome",
                                                value=ident.get("proprietario_nome", ""), key="v_prop_n")
    ident["proprietario_doc"]  = c10.text_input("Proprietário — CPF/CNPJ",
                                                 value=ident.get("proprietario_doc", ""), key="v_prop_d")
    ident["imobiliaria"]       = st.text_input("Imobiliária (se houver)",
                                                value=ident.get("imobiliaria", ""), key="v_imob")
    ident["vistoriador_nome"]  = st.text_input("Vistoriador",
                                                value=ident.get("vistoriador_nome", ""), key="v_vist")

    st.divider()
    st.button("Próximo: Cômodos →", type="primary", use_container_width=is_mobile,
              on_click=_cb_ir_para, args=(2,))


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 2 — CÔMODOS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Foto: upload unificado (câmera nativa no mobile, arquivo no desktop) ────────

def _widget_foto(comodo: dict, item_idx: int, item: dict, mobile: bool):
    """Mobile: abre câmera nativa via file input. Desktop: seleção de arquivo."""
    cid = comodo["id"]
    fotos_salvas = [f for f in item.get("fotos", []) if f.get("bytes")]
    n_fotos = len(fotos_salvas)

    if mobile:
        # Chave muda a cada foto adicionada → widget reseta → permite nova captura
        up = st.file_uploader(
            "📷 Tirar foto",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=False,
            key=f"foto_mob_{cid}_{item_idx}_{n_fotos}",
            help="Toque para abrir a câmera. Pode adicionar várias fotos.",
        )
        if up is not None:
            item.setdefault("fotos", []).append({"nome": up.name, "bytes": up.read()})
            st.rerun()
    else:
        # Desktop: seleção múltipla — chave muda para acumular (append)
        novos = st.file_uploader(
            "📁 Adicionar foto(s)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"foto_desk_{cid}_{item_idx}_{n_fotos}",
            help="Selecione uma ou mais fotos.",
        )
        if novos:
            for f in novos:
                item.setdefault("fotos", []).append({"nome": f.name, "bytes": f.read()})
            st.rerun()

    # Galeria de todas as fotos acumuladas (mobile e desktop)
    if fotos_salvas:
        st.caption(f"📸 {n_fotos} foto(s)")
        n_cols = 1 if mobile else min(n_fotos, 3)
        cols_f = st.columns(n_cols)
        for fi, fb in enumerate(fotos_salvas):
            if fb.get("bytes"):
                col = cols_f[fi % n_cols]
                col.image(fb["bytes"], use_container_width=True)
                if col.button("🗑️", key=f"del_f_{cid}_{item_idx}_{fi}", help="Remover foto"):
                    item["fotos"].pop(fi)
                    st.rerun()


# ── Renderização de um item — MOBILE (um item por tela) ──────────────────────

def _render_item_mobile(comodo: dict, ci: int):
    """Fluxo item a item para mobile: navega um item de cada vez."""
    itens = comodo.get("itens") or []
    if not itens:
        st.info("Este cômodo não tem itens. Adicione um abaixo.")
        return

    n_itens = len(itens)
    ii = st.session_state.get(_K_ITEM) or 0
    ii = max(0, min(ii, n_itens - 1))
    st.session_state[_K_ITEM] = ii

    item = itens[ii]

    # Cabeçalho: nome do cômodo + progresso
    st.markdown(f"**{comodo.get('icone', '🏠')} {comodo.get('nome', '')}**")
    n_preenchidos = sum(1 for it in itens if it.get("estado"))
    st.progress(n_preenchidos / n_itens,
                text=f"{n_preenchidos}/{n_itens} itens com estado")
    st.caption(f"Item {ii + 1} de {n_itens}")
    st.divider()

    # ── Item atual ────────────────────────────────────────────────────────────
    tipo_vist = _dados().get("tipo", "entrada")
    comodo_ent: dict = {}
    if tipo_vist == "saida":
        dados_ent = st.session_state.get("vistoria_entrada_dados") or {}
        comodo_ent = next(
            (c for c in (dados_ent.get("comodos") or [])
             if c.get("nome", "").lower() == comodo.get("nome", "").lower()),
            {}
        )

    item_ent = next(
        (it for it in (comodo_ent.get("itens") or [])
         if it.get("nome", "").lower() == item.get("nome", "").lower()),
        None
    ) if tipo_vist == "saida" else None

    st.subheader(item.get("nome", f"Item {ii + 1}"))
    if item_ent:
        est_ent = item_ent.get("estado", "—")
        st.caption(f"Na entrada: **{est_ent}**")

    opcoes_est = [""] + VT.ESTADOS
    idx_est = opcoes_est.index(item["estado"]) if item.get("estado") in VT.ESTADOS else 0
    item["estado"] = st.selectbox(
        "Estado *", opcoes_est, index=idx_est,
        key=f"est_{comodo['id']}_{ii}",
    )
    item["obs"] = st.text_area(
        "Observação",
        value=item.get("obs", ""),
        placeholder="Descreva o estado com detalhes...",
        key=f"obs_{comodo['id']}_{ii}",
        height=80,
    )

    st.divider()
    _widget_foto(comodo, ii, item, mobile=True)

    # ── Navegação ─────────────────────────────────────────────────────────────
    st.divider()
    c_prev, c_next = st.columns(2)

    with c_prev:
        if ii > 0:
            st.button("← Anterior", use_container_width=True,
                      on_click=_cb_set_item, args=(ii - 1,))
        else:
            st.button("← Lista", use_container_width=True,
                      on_click=_cb_voltar_lista)

    with c_next:
        if ii < n_itens - 1:
            st.button("Próximo item →", type="primary", use_container_width=True,
                      on_click=_cb_set_item, args=(ii + 1,))
        else:
            st.button("✅ Concluir cômodo", type="primary", use_container_width=True,
                      on_click=_cb_concluir_comodo, args=(ci,))

    # Obs geral do cômodo (só no último item, colapsada)
    if ii == n_itens - 1:
        comodo["obs_geral"] = st.text_area(
            "Obs. gerais do cômodo (opcional)",
            value=comodo.get("obs_geral", ""),
            key=f"obs_comodo_{ci}",
            height=70,
        )
        # ── Adicionar novo item ───────────────────────────────────────────────
        with st.expander("➕ Adicionar item ao cômodo"):
            nome_novo = st.text_input("Nome do item", key=f"novo_item_mob_{ci}",
                                       placeholder="Ex.: Armário, Rodapé, Ar-condicionado")
            if st.button("Adicionar", key=f"btn_item_mob_{ci}") and nome_novo.strip():
                comodo.setdefault("itens", []).append(
                    {"nome": nome_novo.strip(), "estado": "", "obs": "", "fotos": []}
                )
                st.session_state[_K_ITEM] = len(comodo["itens"]) - 1
                st.rerun()


# ── Renderização de um item — DESKTOP (todos os itens visíveis) ───────────────

def _render_item_desktop(comodo: dict, item_idx: int, item: dict, item_entrada: dict | None):
    with st.container(border=True):
        col_form, col_foto = st.columns([2, 1])
        with col_form:
            st.markdown(f"**{item.get('nome', f'Item {item_idx + 1}')}**")
            if item_entrada:
                st.caption(f"Na entrada: **{item_entrada.get('estado', '—')}**")
            opcoes_est = [""] + VT.ESTADOS
            idx_est = opcoes_est.index(item["estado"]) if item.get("estado") in VT.ESTADOS else 0
            item["estado"] = st.selectbox(
                "Estado", opcoes_est, index=idx_est,
                key=f"est_{comodo['id']}_{item_idx}",
                label_visibility="collapsed",
            )
            item["obs"] = st.text_input(
                "Observação", value=item.get("obs", ""),
                placeholder="Detalhes relevantes...",
                key=f"obs_{comodo['id']}_{item_idx}",
            )
        with col_foto:
            _widget_foto(comodo, item_idx, item, mobile=False)


# ── Detalhe de um cômodo (mobile ou desktop) ──────────────────────────────────

def _render_detalhe_comodo(ci: int):
    dados = _dados()
    comodos = dados.get("comodos") or []
    if ci >= len(comodos):
        st.error("Cômodo não encontrado.")
        st.session_state[_K_COMODO] = None
        st.rerun()
        return
    comodo = comodos[ci]

    if is_mobile:
        # Mobile: fluxo item a item
        _render_item_mobile(comodo, ci)
    else:
        # Desktop: todos os itens visíveis
        tipo_vist = dados.get("tipo", "entrada")
        comodo_ent: dict = {}
        if tipo_vist == "saida":
            dados_ent = st.session_state.get("vistoria_entrada_dados") or {}
            comodo_ent = next(
                (c for c in (dados_ent.get("comodos") or [])
                 if c.get("nome", "").lower() == comodo.get("nome", "").lower()),
                {}
            )

        c_back, c_title = st.columns([1, 4])
        with c_back:
            st.button("← Lista", use_container_width=True, on_click=_cb_voltar_lista)
        with c_title:
            comodo["nome"] = st.text_input("Nome do cômodo",
                                            value=comodo.get("nome", ""),
                                            key=f"nome_comodo_{ci}")

        if tipo_vist == "saida" and comodo_ent:
            st.info("🔄 Comparativo ativo: estado da entrada exibido ao lado de cada item.")

        itens_ent = comodo_ent.get("itens") or []
        for ii, item in enumerate(comodo.get("itens") or []):
            item_ent = next(
                (i for i in itens_ent
                 if i.get("nome", "").lower() == item.get("nome", "").lower()),
                None
            ) if tipo_vist == "saida" else None
            _render_item_desktop(comodo, ii, item, item_ent)

        with st.expander("➕ Adicionar item"):
            nome_novo = st.text_input("Nome do item", key=f"novo_item_{ci}")
            if st.button("Adicionar", key=f"btn_item_{ci}") and nome_novo.strip():
                comodo.setdefault("itens", []).append(
                    {"nome": nome_novo.strip(), "estado": "", "obs": "", "fotos": []}
                )
                st.rerun()

        st.divider()
        comodo["obs_geral"] = st.text_area(
            "Observações gerais do cômodo",
            value=comodo.get("obs_geral", ""),
            key=f"obs_comodo_{ci}",
            height=80,
        )
        st.divider()
        c_concluir, c_voltar = st.columns(2)
        with c_concluir:
            st.button("✅ Marcar como concluído", type="primary", use_container_width=True,
                      on_click=_cb_concluir_comodo, args=(ci,))
        with c_voltar:
            st.button("← Salvar e voltar", use_container_width=True,
                      on_click=_cb_voltar_lista)


# ── Panel de inclusão de cômodo ───────────────────────────────────────────────

def _render_panel_incluir_comodo():
    comodos = _dados().setdefault("comodos", [])
    with st.container(border=True):
        st.markdown("**Escolha um cômodo:**")
        n_cols = 2 if is_mobile else 3
        cols = st.columns(n_cols)
        for i, (icone, nome) in enumerate(_COMODOS_RAPIDOS):
            def _add_comodo(icone=icone, nome=nome):
                st.session_state[_K_DADOS].setdefault("comodos", []).append(
                    VT.novo_comodo(nome, icone)
                )
                st.session_state[_K_ADICIONANDO] = False
            cols[i % n_cols].button(
                f"{icone} {nome}", key=f"qr_{i}", use_container_width=True,
                on_click=_add_comodo
            )

        st.divider()
        st.markdown("**Personalizado:**")
        c_n, c_i, c_btn = st.columns([3, 1, 1])
        c_n.text_input("Nome", placeholder="Ex.: Varanda Gourmet",
                        key="inc_custom_nome", label_visibility="collapsed")
        c_i.selectbox("", VT.ICONES_DISPONIVEIS,
                       key="inc_custom_icone", label_visibility="collapsed")

        def _add_comodo_custom():
            nome = st.session_state.get("inc_custom_nome", "").strip()
            icone = st.session_state.get("inc_custom_icone", VT.ICONES_DISPONIVEIS[0])
            if nome:
                st.session_state[_K_DADOS].setdefault("comodos", []).append(
                    VT.novo_comodo(nome, icone)
                )
                st.session_state[_K_ADICIONANDO] = False

        c_btn.button("Incluir", key="inc_custom_btn", on_click=_add_comodo_custom)

        st.button("✕ Fechar", key="inc_fechar", use_container_width=False,
                  on_click=_cb_fechar_adicionando)


# ── Lista de cômodos (cards) ──────────────────────────────────────────────────

def _render_lista_comodos():
    comodos = _dados().setdefault("comodos", [])
    conc, tot = _progresso_comodos()

    st.button("➕ Incluir cômodo", use_container_width=is_mobile,
              on_click=_cb_toggle_adicionando)

    # Panel de seleção (aparece logo após o botão quando ativo)
    if st.session_state.get(_K_ADICIONANDO):
        _render_panel_incluir_comodo()

    st.divider()

    # Sem cômodos ainda
    if not comodos:
        st.info("Nenhum cômodo adicionado. Toque em **Incluir cômodo** para começar.")
    else:
        # Barra de progresso
        if tot:
            st.caption(f"{conc}/{tot} cômodos concluídos")
            st.progress(conc / tot)
            st.divider()

        # Cards dos cômodos
        for ci, comodo in enumerate(comodos):
            nome   = comodo.get("nome", f"Cômodo {ci + 1}")
            icone  = comodo.get("icone", "🏠")
            conc_c = comodo.get("concluido", False)
            badge  = "✅ Concluído" if conc_c else "⏳ Pendente"
            cor    = "#10B981" if conc_c else "#F59E0B"
            n_i    = len(comodo.get("itens") or [])
            n_p    = sum(1 for it in (comodo.get("itens") or []) if it.get("estado"))

            with st.container(border=True):
                c_info, c_btn = st.columns([3, 1])
                with c_info:
                    st.markdown(f"### {icone} {nome}")
                    st.markdown(
                        f"<span style='color:{cor};font-size:13px;font-weight:600'>"
                        f"{badge}</span>",
                        unsafe_allow_html=True,
                    )
                    if n_i:
                        st.caption(f"{n_p}/{n_i} itens avaliados")
                with c_btn:
                    lbl = "✏️ Revisar" if conc_c else "🔍 Inspecionar"
                    st.button(lbl, key=f"ins_{ci}", use_container_width=True,
                              on_click=_cb_abrir_comodo, args=(ci,))
                    if conc_c:
                        st.button("↩️", key=f"unconcl_{ci}",
                                  help="Desmarcar como concluído",
                                  use_container_width=True,
                                  on_click=_cb_desmarcar_comodo, args=(ci,))
                    st.button("🗑️", key=f"del_c_{ci}", help="Remover",
                              use_container_width=True,
                              on_click=_cb_remover_comodo, args=(ci,))

    # Navegação inferior
    st.divider()
    c_prev, c_next = st.columns(2)
    with c_prev:
        st.button("← Identificação", use_container_width=True,
                  on_click=_cb_ir_para, args=(1,))
    with c_next:
        if tot == 0 or conc < tot:
            st.button(
                "Fechamento →" if tot == 0 else f"Fechamento → ({tot - conc} pendente(s))",
                use_container_width=True, disabled=True,
                help="Conclua todos os cômodos antes de avançar.",
            )
        else:
            st.button("Próximo: Fechamento →", type="primary", use_container_width=True,
                      on_click=_cb_ir_para, args=(3,))


def _render_passo_2():
    st.subheader("Vistoria dos Cômodos")
    ci = st.session_state.get(_K_COMODO)
    if ci is not None:
        _render_detalhe_comodo(ci)
    else:
        _render_lista_comodos()


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 3 — FECHAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

_MEDIDORES_DEF = [
    ("medidor_agua", "fotos_agua", "💧 Água",  "v_agua"),
    ("medidor_luz",  "fotos_luz",  "⚡ Luz",   "v_luz"),
    ("medidor_gas",  "fotos_gas",  "🔥 Gás",   "v_gas"),
]


def _render_passo_3():
    dados = _dados()
    fech  = dados.setdefault("fechamento", {})

    st.subheader("Fechamento e Laudo")
    st.markdown("**Chaves entregues**")
    fech["chaves_quantidade"] = st.number_input(
        "Chaves", min_value=0, max_value=20,
        value=int(fech.get("chaves_quantidade") or 2), key="v_chaves",
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**Medidores**")
    n_cols_med = 1 if is_mobile else 3
    med_cols = st.columns(n_cols_med)
    for col_i, (campo_val, campo_foto, label, key_val) in enumerate(_MEDIDORES_DEF):
        with med_cols[col_i % n_cols_med]:
            st.markdown(f"**{label}**")
            fech[campo_val] = st.text_input(
                "Leitura", value=fech.get(campo_val, ""),
                key=key_val, label_visibility="collapsed",
                placeholder="Ex.: 1234,5",
            )
            fotos_med = fech.setdefault(campo_foto, [])
            n_f_med = len([f for f in fotos_med if f.get("bytes") or f.get("caminho")])
            up_med = st.file_uploader(
                "Foto do medidor", type=["jpg", "jpeg", "png"],
                accept_multiple_files=False,
                key=f"{key_val}_foto_{n_f_med}",
                label_visibility="collapsed",
            )
            if up_med is not None:
                fotos_med.append({"nome": up_med.name, "bytes": up_med.read()})
                st.rerun()
            if n_f_med:
                st.caption(f"📸 {n_f_med} foto(s)")
                first_med = next((f for f in fotos_med if f.get("bytes")), None)
                if first_med:
                    st.image(first_med["bytes"], use_container_width=True)
                for fi_m, _ in enumerate(fotos_med):
                    if st.button("🗑️", key=f"del_{campo_foto}_{fi_m}", help="Remover foto"):
                        fotos_med.pop(fi_m)
                        st.rerun()

    st.divider()
    fech["obs_gerais"] = st.text_area(
        "Observações gerais do imóvel",
        value=fech.get("obs_gerais", ""),
        height=120, key="v_obs_gerais",
        placeholder="Condições gerais, pendências, ressalvas...",
    )

    st.divider()
    st.markdown("**Gerar Laudo PDF**")
    st.caption(
        "O laudo inclui identificação das partes, medidores, vistoria por cômodo "
        "com fotos e estados, base legal (Lei 8.245/91) e página de assinaturas."
    )

    dados_entrada: dict | None = None
    if dados.get("tipo") == "saida" and dados.get("vistoria_entrada_id"):
        dados_entrada = st.session_state.get("vistoria_entrada_dados")
        if not dados_entrada:
            try:
                row = VDB.obter(dados["vistoria_entrada_id"], user_id=_USER_ID)
                dados_entrada = row.get("dados") if row else None
            except Exception:
                dados_entrada = None
        if dados_entrada:
            st.success("✅ Comparativo entrada × saída incluído no laudo.")
        else:
            st.warning("⚠️ Vistoria de entrada não encontrada — comparativo indisponível.")

    _PDF_CACHE = "vistoria_pdf_cache"

    # ── PDF download — sempre visível ────────────────────────────────────────
    pdf_bytes = st.session_state.get(_PDF_CACHE)
    if pdf_bytes is None:
        try:
            pdf_bytes = PDFVIST.gerar_laudo(dados, avaliador=_AVALIADOR,
                                             dados_entrada=dados_entrada)
            st.session_state[_PDF_CACHE] = pdf_bytes
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
    if pdf_bytes:
        ident = dados.get("identificacao") or {}
        slug  = (ident.get("endereco") or "vistoria").replace(" ", "_")[:30]
        nome_arq = f"Laudo_Vistoria_{dados.get('tipo','').capitalize()}_{slug}.pdf"
        st.download_button("📄 Baixar Laudo PDF", data=pdf_bytes,
                            file_name=nome_arq, mime="application/pdf",
                            use_container_width=True, type="secondary")

    st.divider()

    # ── Salvar e finalizar ───────────────────────────────────────────────────
    if st.button("💾 Salvar e finalizar", type="primary", use_container_width=True):
        try:
            # Gera PDF antes de subir fotos (bytes ainda em memória)
            try:
                _pdf_temp = PDFVIST.gerar_laudo(dados, avaliador=_AVALIADOR,
                                                 dados_entrada=dados_entrada)
                st.session_state[_PDF_CACHE] = _pdf_temp
            except Exception:
                pass

            with st.spinner("Salvando vistoria..."):
                vid = _salvar_rascunho()
                st.session_state[_K_ID] = vid

            # Upload fotos dos cômodos — falha não cancela o salvamento
            try:
                with st.spinner("Enviando fotos dos cômodos..."):
                    comodos_meta = VAN.salvar_fotos_vistoria(
                        vid, dados.get("comodos") or []
                    )
                    dados["comodos"] = comodos_meta
            except Exception as e_foto:
                st.warning(f"⚠️ Fotos dos cômodos não armazenadas: {e_foto}")

            # Upload fotos dos medidores
            try:
                with st.spinner("Enviando fotos dos medidores..."):
                    fech_meta = VAN.salvar_fotos_fechamento(
                        vid, dados.get("fechamento") or {}
                    )
                    dados["fechamento"] = fech_meta
            except Exception as e_med:
                st.warning(f"⚠️ Fotos dos medidores não armazenadas: {e_med}")

            # Marca como concluído independente do resultado das fotos
            VDB.salvar(dados, user_id=_USER_ID, vistoria_id=vid,
                       status=VDB.STATUS_CONCLUIDO)
            st.success(
                f"✅ Vistoria #{vid} salva no histórico! "
                "Use o histórico para baixar o laudo com fotos."
            )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    st.divider()
    with st.expander("⚖️ Embasamento legal"):
        st.write(PDFVIST.DISCLAIMER_VISTORIA)
        st.caption(
            "Para validade jurídica plena, colete assinaturas físicas das partes "
            "no ato da vistoria, ou utilize uma plataforma certificada "
            "(ClickSign, ZapSign) para assinatura eletrônica."
        )

    st.divider()
    st.button("← Voltar aos Cômodos", use_container_width=is_mobile,
              on_click=_cb_ir_para, args=(2,))


# ── Roteamento ────────────────────────────────────────────────────────────────
if passo_atual == 1:
    _render_passo_1()
elif passo_atual == 2:
    _render_passo_2()
elif passo_atual == 3:
    _render_passo_3()
