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
_K_DADOS  = "vistoria"
_K_ID     = "vistoria_id"
_K_PASSO  = "vistoria_passo"
_K_COMODO = "vistoria_comodo_idx"
_K_ITEM   = "vistoria_item_idx"
_K_RESET  = "_resetar_vistoria"

_RESET_KEYS = [_K_DADOS, _K_ID, _K_PASSO, _K_COMODO, _K_ITEM, "vistoria_entrada_dados"]

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
    st.rerun()


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
            if st.button(label, key=f"step_{i}", use_container_width=True):
                _ir_para(i)

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
    if st.button("Próximo: Cômodos →", type="primary", use_container_width=is_mobile):
        _ir_para(2)


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 2 — CÔMODOS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Foto: widget unificado (câmera + galeria) ─────────────────────────────────

def _widget_foto(comodo: dict, item_idx: int, item: dict, mobile: bool):
    """Renderiza a captura de foto: câmera (mobile) ou arquivo (desktop)."""
    cid = comodo["id"]
    fotos_salvas = [f for f in item.get("fotos", []) if f.get("bytes")]

    if mobile:
        # ── Câmera como primário ──────────────────────────────────────────────
        foto_cam = st.camera_input(
            "📷 Tirar foto",
            key=f"cam_{cid}_{item_idx}",
            help="Aponte para o item e capture a foto.",
        )
        if foto_cam is not None:
            item["fotos"] = [{"nome": f"foto_{item['nome'].replace('/', '_')}.jpg",
                               "bytes": foto_cam.getvalue()}]
            fotos_salvas = item["fotos"]

        # Preview da foto salva (se câmera ainda não tem nada novo)
        if not foto_cam and fotos_salvas:
            st.image(fotos_salvas[0]["bytes"],
                     caption="✅ Foto registrada", use_container_width=True)

        # Galeria como alternativa
        with st.expander("📁 ou escolher da galeria"):
            up = st.file_uploader(
                "Selecionar arquivo",
                type=["jpg", "jpeg", "png"],
                key=f"up_{cid}_{item_idx}",
                label_visibility="collapsed",
            )
            if up:
                item["fotos"] = [{"nome": up.name, "bytes": up.read()}]
                st.rerun()

    else:
        # ── Arquivo como primário (desktop) ───────────────────────────────────
        novos = st.file_uploader(
            "📎 Fotos",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"up_{cid}_{item_idx}",
        )
        if novos:
            item["fotos"] = [{"nome": f.name, "bytes": f.read()} for f in novos]
            fotos_salvas = item["fotos"]

        # Preview
        if fotos_salvas:
            cols_f = st.columns(min(len(fotos_salvas), 3))
            for col, fb in zip(cols_f, fotos_salvas[:3]):
                col.image(fb["bytes"], use_container_width=True)
            if len(fotos_salvas) > 3:
                st.caption(f"+{len(fotos_salvas) - 3} foto(s)")
            if st.button("🗑️ Limpar fotos", key=f"del_f_{cid}_{item_idx}"):
                item["fotos"] = []
                st.rerun()

        # Câmera como opção adicional no desktop
        with st.expander("📷 Usar câmera"):
            foto_cam = st.camera_input("", key=f"cam_{cid}_{item_idx}",
                                       label_visibility="collapsed")
            if foto_cam is not None:
                item["fotos"] = [{"nome": f"foto_{item['nome'].replace('/', '_')}.jpg",
                                   "bytes": foto_cam.getvalue()}]
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
            if st.button("← Anterior", use_container_width=True):
                st.session_state[_K_ITEM] = ii - 1
                st.rerun()
        else:
            if st.button("← Lista", use_container_width=True):
                st.session_state[_K_COMODO] = None
                st.session_state[_K_ITEM] = None
                st.rerun()

    with c_next:
        if ii < n_itens - 1:
            if st.button("Próximo item →", type="primary", use_container_width=True):
                st.session_state[_K_ITEM] = ii + 1
                st.rerun()
        else:
            # Último item — opção de concluir
            if st.button("✅ Concluir cômodo", type="primary", use_container_width=True):
                comodo["concluido"] = True
                st.session_state[_K_COMODO] = None
                st.session_state[_K_ITEM] = None
                st.rerun()

    # Obs geral do cômodo (só no último item, colapsada)
    if ii == n_itens - 1:
        comodo["obs_geral"] = st.text_area(
            "Obs. gerais do cômodo (opcional)",
            value=comodo.get("obs_geral", ""),
            key=f"obs_comodo_{ci}",
            height=70,
        )


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
            if st.button("← Lista", use_container_width=True):
                st.session_state[_K_COMODO] = None
                st.rerun()
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
            if st.button("✅ Marcar como concluído", type="primary", use_container_width=True):
                comodo["concluido"] = True
                st.session_state[_K_COMODO] = None
                st.rerun()
        with c_voltar:
            if st.button("← Salvar e voltar", use_container_width=True):
                st.session_state[_K_COMODO] = None
                st.rerun()


# ── Lista de cômodos ──────────────────────────────────────────────────────────

def _render_lista_comodos():
    dados = _dados()
    comodos = dados.setdefault("comodos", [])
    conc, tot = _progresso_comodos()

    st.markdown(f"**{conc}/{tot} cômodos vistoriados**")
    if tot:
        st.progress(conc / tot)

    if is_mobile:
        st.caption("Toque em **Inspecionar** para vistoriar cômodo a cômodo.")
    else:
        st.caption("Clique em **Inspecionar** para abrir o cômodo.")
    st.divider()

    for ci, comodo in enumerate(comodos):
        nome    = comodo.get("nome", f"Cômodo {ci + 1}")
        icone   = comodo.get("icone", "🏠")
        conc_c  = comodo.get("concluido", False)
        badge   = "✅ Concluído" if conc_c else "⏳ Pendente"
        cor     = "#10B981" if conc_c else "#F59E0B"
        n_i     = len(comodo.get("itens") or [])
        n_p     = sum(1 for it in (comodo.get("itens") or []) if it.get("estado"))

        with st.container(border=True):
            c_info, c_btn = st.columns([3, 1])
            with c_info:
                st.markdown(f"{icone} **{nome}**")
                st.markdown(f"<span style='color:{cor};font-size:12px;'>{badge}</span>",
                            unsafe_allow_html=True)
                if n_i:
                    st.caption(f"{n_p}/{n_i} itens com estado")
            with c_btn:
                lbl = "✏️ Revisar" if conc_c else "🔍 Inspecionar"
                if st.button(lbl, key=f"ins_{ci}", use_container_width=True):
                    st.session_state[_K_COMODO] = ci
                    st.session_state[_K_ITEM] = 0  # começa do primeiro item no mobile
                    st.rerun()
                if conc_c:
                    if st.button("↩️", key=f"unconcl_{ci}",
                                 help="Desmarcar como concluído",
                                 use_container_width=True):
                        comodo["concluido"] = False
                        st.rerun()
                if st.button("🗑️", key=f"del_c_{ci}", help="Remover cômodo",
                             use_container_width=True):
                    comodos.pop(ci)
                    st.rerun()

    st.divider()
    with st.expander("➕ Adicionar cômodo"):
        col_n, col_i = st.columns([3, 1])
        nome_novo  = col_n.text_input("Nome", placeholder="Ex.: Quarto 2", key="novo_comodo_nome")
        icone_novo = col_i.selectbox("Ícone", VT.ICONES_DISPONIVEIS, key="novo_comodo_icone")
        if st.button("Adicionar cômodo", key="btn_add_comodo") and nome_novo.strip():
            comodos.append(VT.novo_comodo(nome_novo.strip(), icone_novo))
            st.rerun()

    st.divider()
    c_prev, c_next = st.columns(2)
    with c_prev:
        if st.button("← Identificação", use_container_width=True):
            _ir_para(1)
    with c_next:
        if conc < tot:
            st.button(
                f"Fechamento → ({tot - conc} pendente(s))",
                use_container_width=True, disabled=True,
                help="Conclua todos os cômodos antes de avançar.",
            )
        else:
            if st.button("Próximo: Fechamento →", type="primary", use_container_width=True):
                _ir_para(3)


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

def _render_passo_3():
    dados = _dados()
    fech  = dados.setdefault("fechamento", {})

    st.subheader("Fechamento e Laudo")
    st.markdown("**Chaves e medidores**")

    c1, c2, c3, c4 = st.columns(4)
    fech["chaves_quantidade"] = c1.number_input(
        "Chaves", min_value=0, max_value=20,
        value=int(fech.get("chaves_quantidade") or 2), key="v_chaves",
    )
    fech["medidor_agua"] = c2.text_input("Água",  value=fech.get("medidor_agua", ""), key="v_agua")
    fech["medidor_luz"]  = c3.text_input("Luz",   value=fech.get("medidor_luz", ""),  key="v_luz")
    fech["medidor_gas"]  = c4.text_input("Gás",   value=fech.get("medidor_gas", ""),  key="v_gas")

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

    col_salvar, col_pdf = st.columns(2)
    with col_salvar:
        if st.button("💾 Salvar e finalizar", type="primary", use_container_width=True):
            try:
                with st.spinner("Salvando e subindo fotos..."):
                    vid = _salvar_rascunho()
                    comodos_meta = VAN.salvar_fotos_vistoria(vid, dados.get("comodos") or [])
                    dados["comodos"] = comodos_meta
                    VDB.salvar(dados, user_id=_USER_ID, vistoria_id=vid,
                               status=VDB.STATUS_CONCLUIDO)
                    st.session_state[_K_ID] = vid
                st.success(f"✅ Vistoria #{vid} salva!")
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    with col_pdf:
        try:
            pdf_bytes = PDFVIST.gerar_laudo(dados, avaliador=_AVALIADOR,
                                             dados_entrada=dados_entrada)
            ident = dados.get("identificacao") or {}
            slug  = (ident.get("endereco") or "vistoria").replace(" ", "_")[:30]
            nome_arq = f"Laudo_Vistoria_{dados.get('tipo','').capitalize()}_{slug}.pdf"
            st.download_button("📄 Baixar Laudo PDF", data=pdf_bytes,
                                file_name=nome_arq, mime="application/pdf",
                                use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

    st.divider()
    with st.expander("⚖️ Embasamento legal"):
        st.write(PDFVIST.DISCLAIMER_VISTORIA)
        st.caption(
            "Para validade jurídica plena, colete assinaturas físicas das partes "
            "no ato da vistoria, ou utilize uma plataforma certificada "
            "(ClickSign, ZapSign) para assinatura eletrônica."
        )

    st.divider()
    if st.button("← Voltar aos Cômodos", use_container_width=is_mobile):
        _ir_para(2)


# ── Roteamento ────────────────────────────────────────────────────────────────
if passo_atual == 1:
    _render_passo_1()
elif passo_atual == 2:
    _render_passo_2()
elif passo_atual == 3:
    _render_passo_3()
