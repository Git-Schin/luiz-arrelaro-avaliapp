"""
Wizard de Vistoria de Imóvel para Locação.

Três passos:
  1. Identificação  — imóvel, data, partes envolvidas
  2. Cômodos        — cômodo a cômodo: itens, estado, obs, fotos
  3. Fechamento     — medidores, chaves, observações gerais, gerar laudo PDF
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

# ── Constantes de keys do session_state ──────────────────────────────────────
_K_DADOS    = "vistoria"
_K_ID       = "vistoria_id"
_K_PASSO    = "vistoria_passo"
_K_COMODO   = "vistoria_comodo_idx"
_K_RESET    = "_resetar_vistoria"

_RESET_KEYS = [_K_DADOS, _K_ID, _K_PASSO, _K_COMODO, "vistoria_entrada_dados"]

# ── Reset ─────────────────────────────────────────────────────────────────────
if st.session_state.pop(_K_RESET, False):
    for k in _RESET_KEYS:
        st.session_state.pop(k, None)

# ── Inicializar estado vazio ──────────────────────────────────────────────────
_perfil = st.session_state.get("perfil") or {}
if _K_DADOS not in st.session_state:
    st.session_state[_K_DADOS] = VT.dados_vistoria_vazio(_perfil)
if _K_PASSO not in st.session_state:
    st.session_state[_K_PASSO] = 1
if _K_COMODO not in st.session_state:
    st.session_state[_K_COMODO] = None

_USER_ID = st.session_state.get("user_id")
_AVALIADOR = _perfil


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dados() -> dict:
    return st.session_state[_K_DADOS]


def _ir_para(passo: int):
    st.session_state[_K_PASSO] = passo
    st.session_state[_K_COMODO] = None
    st.rerun()


def _salvar_rascunho() -> int:
    vid = st.session_state.get(_K_ID)
    vid = VDB.salvar_rascunho(_dados(), user_id=_USER_ID, vistoria_id=vid)
    st.session_state[_K_ID] = vid
    return vid


def _salvar_final() -> int:
    dados = _dados()
    vid = st.session_state.get(_K_ID)
    # Sobe fotos para o Storage
    if vid:
        comodos_com_meta = VAN.salvar_fotos_vistoria(vid, dados.get("comodos") or [])
        dados["comodos"] = comodos_com_meta
    vid = VDB.salvar(dados, user_id=_USER_ID, vistoria_id=vid,
                     status=VDB.STATUS_CONCLUIDO)
    st.session_state[_K_ID] = vid
    return vid


def _progresso_comodos() -> tuple[int, int]:
    comodos = _dados().get("comodos") or []
    total = len(comodos)
    concluidos = sum(1 for c in comodos if c.get("concluido"))
    return concluidos, total


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

    # Tipo e vinculação com entrada (se saída)
    tipo_opcoes = {"Vistoria de Entrada (início da locação)": "entrada",
                   "Vistoria de Saída (fim da locação)": "saida"}
    tipo_label_atual = next(
        (k for k, v in tipo_opcoes.items() if v == dados.get("tipo", "entrada")),
        list(tipo_opcoes.keys())[0]
    )
    tipo_sel = st.radio("Tipo de vistoria", list(tipo_opcoes.keys()),
                        index=list(tipo_opcoes.keys()).index(tipo_label_atual),
                        horizontal=True)
    dados["tipo"] = tipo_opcoes[tipo_sel]

    if dados["tipo"] == "saida":
        st.info("ℹ️ Vistoria de saída: os estados registrados na entrada serão exibidos lado a lado para comparação.")
        try:
            entradas = VDB.listar_entradas_concluidas(user_id=_USER_ID)
        except Exception:
            entradas = []
        if entradas:
            opcoes_ent = {
                f"#{e['id']} · {e.get('endereco', '')} · {e.get('locatario_nome', '')} · {e.get('data_vistoria', '')}": e["id"]
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
            st.warning("Nenhuma vistoria de entrada concluída encontrada. Finalize uma vistoria de entrada primeiro.")

    st.divider()

    # ── Endereço ──────────────────────────────────────────────────────────────
    st.markdown("**Endereço do imóvel**")
    c1, c2 = st.columns([2, 1])
    cep_val = c1.text_input("CEP", value=ident.get("cep", ""),
                             placeholder="00000-000", key="v_cep")
    ident["cep"] = cep_val

    if c2.button("🔍 Buscar CEP", use_container_width=True):
        resultado = CEP.buscar_cep(cep_val)
        if resultado:
            ident["endereco"] = resultado.get("logradouro", "")
            ident["bairro"] = resultado.get("bairro", "")
            ident["cidade_uf"] = resultado.get("cidade_uf", "")
            st.toast(f"CEP localizado em {resultado.get('cidade_uf', '')}", icon="📍")
            st.rerun()
        else:
            st.warning("CEP não encontrado. Preencha o endereço manualmente.")

    c3, c4 = st.columns([3, 1])
    ident["endereco"] = c3.text_input("Logradouro / Rua",
                                       value=ident.get("endereco", ""), key="v_end")
    ident["numero"] = c4.text_input("Número", value=ident.get("numero", ""), key="v_num")

    c5, c6 = st.columns(2)
    ident["bairro"] = c5.text_input("Bairro", value=ident.get("bairro", ""), key="v_bai")
    ident["cidade_uf"] = c6.text_input("Cidade/UF", value=ident.get("cidade_uf", ""),
                                        placeholder="Campinas/SP", key="v_cuf")

    st.divider()

    # ── Data da vistoria ──────────────────────────────────────────────────────
    data_str = ident.get("data_vistoria")
    try:
        data_val = date.fromisoformat(str(data_str)) if data_str else date.today()
    except Exception:
        data_val = date.today()
    nova_data = st.date_input("📅 Data da vistoria", value=data_val, key="v_data")
    ident["data_vistoria"] = nova_data.isoformat() if nova_data else None

    st.divider()

    # ── Partes ────────────────────────────────────────────────────────────────
    st.markdown("**Partes envolvidas**")
    c7, c8 = st.columns(2)
    ident["locatario_nome"] = c7.text_input("Locatário — nome completo",
                                             value=ident.get("locatario_nome", ""), key="v_loc_n")
    ident["locatario_doc"] = c8.text_input("Locatário — CPF/RG",
                                            value=ident.get("locatario_doc", ""), key="v_loc_d")
    c9, c10 = st.columns(2)
    ident["proprietario_nome"] = c9.text_input("Proprietário / Imobiliária — nome",
                                                value=ident.get("proprietario_nome", ""), key="v_prop_n")
    ident["proprietario_doc"] = c10.text_input("Proprietário — CPF/CNPJ",
                                                value=ident.get("proprietario_doc", ""), key="v_prop_d")
    ident["imobiliaria"] = st.text_input("Imobiliária (se houver)",
                                          value=ident.get("imobiliaria", ""), key="v_imob")
    ident["vistoriador_nome"] = st.text_input("Vistoriador",
                                               value=ident.get("vistoriador_nome", ""), key="v_vist")

    st.divider()
    if st.button("Próximo: Cômodos →", type="primary"):
        _ir_para(2)


# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 2 — CÔMODOS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_item(comodo: dict, item_idx: int, item: dict, item_entrada: dict | None):
    """Renderiza um item de vistoria (estado + obs + fotos)."""
    tipo_vist = _dados().get("tipo", "entrada")
    with st.container(border=True):
        col_form, col_foto = st.columns([2, 1])
        with col_form:
            nome = item.get("nome", f"Item {item_idx + 1}")
            st.markdown(f"**{nome}**")
            if tipo_vist == "saida" and item_entrada is not None:
                est_ent = item_entrada.get("estado", "—")
                st.caption(f"Na entrada: **{est_ent}**")

            opcoes_est = [""] + VT.ESTADOS
            idx_est = opcoes_est.index(item["estado"]) if item.get("estado") in VT.ESTADOS else 0
            novo_est = st.selectbox(
                "Estado", opcoes_est,
                index=idx_est,
                key=f"est_{comodo['id']}_{item_idx}",
                label_visibility="collapsed",
            )
            item["estado"] = novo_est

            novo_obs = st.text_input(
                "Observação", value=item.get("obs", ""),
                placeholder="Descreva detalhes relevantes...",
                key=f"obs_{comodo['id']}_{item_idx}",
            )
            item["obs"] = novo_obs

        with col_foto:
            # Exibe fotos já carregadas
            fotos_bytes = [f for f in item.get("fotos", []) if f.get("bytes")]
            if fotos_bytes:
                for fb in fotos_bytes[:3]:
                    st.image(fb["bytes"], use_container_width=True)
                if len(fotos_bytes) > 3:
                    st.caption(f"+{len(fotos_bytes) - 3} foto(s)")

            up_key = f"up_{comodo['id']}_{item_idx}"
            novos = st.file_uploader(
                "📷 Fotos",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=up_key,
                label_visibility="collapsed",
            )
            if novos:
                item["fotos"] = [{"nome": f.name, "bytes": f.read()} for f in novos]

            if fotos_bytes and st.button("🗑️ Limpar fotos", key=f"del_f_{comodo['id']}_{item_idx}"):
                item["fotos"] = []
                st.rerun()


def _render_detalhe_comodo(ci: int):
    """Renderiza o formulário de vistoria de um cômodo específico."""
    dados = _dados()
    comodos = dados.get("comodos") or []
    if ci >= len(comodos):
        st.error("Cômodo não encontrado.")
        st.session_state[_K_COMODO] = None
        st.rerun()
        return

    comodo = comodos[ci]
    tipo_vist = dados.get("tipo", "entrada")

    # Carrega cômodo equivalente da entrada para comparativo
    comodo_entrada: dict = {}
    if tipo_vist == "saida":
        dados_ent = st.session_state.get("vistoria_entrada_dados") or {}
        comodos_ent = dados_ent.get("comodos") or []
        comodo_entrada = next(
            (c for c in comodos_ent
             if c.get("nome", "").lower() == comodo.get("nome", "").lower()),
            {}
        )

    c_back, c_title = st.columns([1, 4])
    with c_back:
        if st.button("← Lista", use_container_width=True):
            st.session_state[_K_COMODO] = None
            st.rerun()
    with c_title:
        novo_nome = st.text_input("Nome do cômodo",
                                   value=comodo.get("nome", ""),
                                   key=f"nome_comodo_{ci}")
        comodo["nome"] = novo_nome

    if tipo_vist == "saida" and comodo_entrada:
        st.info("🔄 Comparativo ativo: mostrando estado da entrada ao lado de cada item.")

    # Itens
    itens_entrada = comodo_entrada.get("itens") or []
    for ii, item in enumerate(comodo.get("itens") or []):
        item_ent = next(
            (i for i in itens_entrada
             if i.get("nome", "").lower() == item.get("nome", "").lower()),
            None
        ) if tipo_vist == "saida" else None
        _render_item(comodo, ii, item, item_ent)

    # Adicionar item
    with st.expander("➕ Adicionar item a este cômodo"):
        nome_novo_item = st.text_input("Nome do novo item", key=f"novo_item_nome_{ci}")
        if st.button("Adicionar", key=f"btn_add_item_{ci}") and nome_novo_item.strip():
            comodo.setdefault("itens", []).append(
                {"nome": nome_novo_item.strip(), "estado": "", "obs": "", "fotos": []}
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
    col_concluir, col_voltar = st.columns(2)
    with col_concluir:
        if st.button("✅ Marcar como concluído", type="primary", use_container_width=True):
            comodo["concluido"] = True
            st.session_state[_K_COMODO] = None
            st.rerun()
    with col_voltar:
        if st.button("← Salvar e voltar à lista", use_container_width=True):
            st.session_state[_K_COMODO] = None
            st.rerun()


def _render_lista_comodos():
    """Renderiza a lista de cômodos com indicadores de status."""
    dados = _dados()
    comodos = dados.setdefault("comodos", [])
    conc, tot = _progresso_comodos()

    # Barra de progresso
    st.markdown(f"**{conc}/{tot} cômodos vistoriados**")
    if tot > 0:
        st.progress(conc / tot)
    st.caption("Inspecione cada cômodo e marque como concluído para avançar.")
    st.divider()

    # Cards dos cômodos
    for ci, comodo in enumerate(comodos):
        nome = comodo.get("nome", f"Cômodo {ci + 1}")
        icone = comodo.get("icone", "🏠")
        concluido = comodo.get("concluido", False)
        badge = "✅ Concluído" if concluido else "⏳ Pendente"
        cor_badge = "#10B981" if concluido else "#F59E0B"

        with st.container(border=True):
            c_nome, c_btn = st.columns([3, 1])
            with c_nome:
                st.markdown(f"{icone} **{nome}**")
                st.markdown(
                    f"<span style='color:{cor_badge};font-size:12px;'>{badge}</span>",
                    unsafe_allow_html=True,
                )
                n_itens = len(comodo.get("itens") or [])
                n_preenchidos = sum(1 for it in (comodo.get("itens") or []) if it.get("estado"))
                if n_itens:
                    st.caption(f"{n_preenchidos}/{n_itens} itens com estado")
            with c_btn:
                lbl = "✏️ Revisar" if concluido else "🔍 Inspecionar"
                if st.button(lbl, key=f"ins_{ci}", use_container_width=True):
                    st.session_state[_K_COMODO] = ci
                    st.rerun()
                if concluido:
                    if st.button("↩️", key=f"unconcl_{ci}", help="Desmarcar como concluído",
                                 use_container_width=True):
                        comodo["concluido"] = False
                        st.rerun()
                if st.button("🗑️", key=f"del_c_{ci}", help="Remover cômodo",
                             use_container_width=True):
                    comodos.pop(ci)
                    st.rerun()

    st.divider()

    # Adicionar cômodo
    with st.expander("➕ Adicionar cômodo"):
        col_n, col_i = st.columns([3, 1])
        nome_novo = col_n.text_input("Nome", placeholder="Ex.: Quarto 2", key="novo_comodo_nome")
        icone_novo = col_i.selectbox("Ícone", VT.ICONES_DISPONIVEIS, index=0, key="novo_comodo_icone")
        if st.button("Adicionar cômodo", key="btn_add_comodo") and nome_novo.strip():
            comodos.append(VT.novo_comodo(nome_novo.strip(), icone_novo))
            st.rerun()

    st.divider()

    # Navegação
    c_prev, c_next = st.columns(2)
    with c_prev:
        if st.button("← Identificação", use_container_width=True):
            _ir_para(1)
    with c_next:
        if conc < tot:
            st.button(
                f"Próximo: Fechamento → ({tot - conc} pendente(s))",
                use_container_width=True,
                disabled=True,
                help="Conclua todos os cômodos antes de avançar."
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
    fech = dados.setdefault("fechamento", {})

    st.subheader("Fechamento e Laudo")

    st.markdown("**Chaves e medidores**")
    c1, c2, c3, c4 = st.columns(4)
    fech["chaves_quantidade"] = c1.number_input(
        "Chaves entregues",
        min_value=0, max_value=20,
        value=int(fech.get("chaves_quantidade") or 2),
        key="v_chaves",
    )
    fech["medidor_agua"] = c2.text_input("Medidor Água",
                                          value=fech.get("medidor_agua", ""), key="v_agua")
    fech["medidor_luz"] = c3.text_input("Medidor Luz",
                                         value=fech.get("medidor_luz", ""), key="v_luz")
    fech["medidor_gas"] = c4.text_input("Medidor Gás",
                                         value=fech.get("medidor_gas", ""), key="v_gas")

    st.divider()
    fech["obs_gerais"] = st.text_area(
        "Observações gerais do imóvel",
        value=fech.get("obs_gerais", ""),
        height=120,
        key="v_obs_gerais",
        placeholder="Condições gerais da propriedade, pendências, ressalvas...",
    )

    st.divider()
    st.markdown("**Gerar Laudo PDF**")
    st.caption(
        "O laudo inclui: identificação das partes, medidores, vistoria cômodo a cômodo "
        "com fotos e estados, base legal (Lei 8.245/91) e página de assinaturas."
    )

    # Carrega dados da entrada vinculada para comparativo (se saída)
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
            st.success("✅ Comparativo de entrada × saída será incluído no laudo.")
        else:
            st.warning("⚠️ Vistoria de entrada vinculada não encontrada. O comparativo não estará disponível.")

    col_salvar, col_pdf = st.columns(2)

    with col_salvar:
        if st.button("💾 Salvar e finalizar", type="primary", use_container_width=True):
            try:
                with st.spinner("Salvando e subindo fotos..."):
                    vid = _salvar_rascunho()
                    # Sobe fotos
                    comodos_meta = VAN.salvar_fotos_vistoria(vid, dados.get("comodos") or [])
                    dados["comodos"] = comodos_meta
                    VDB.salvar(dados, user_id=_USER_ID, vistoria_id=vid,
                               status=VDB.STATUS_CONCLUIDO)
                    st.session_state[_K_ID] = vid
                st.success(f"✅ Vistoria #{vid} salva com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    with col_pdf:
        try:
            pdf_bytes = PDFVIST.gerar_laudo(
                dados,
                avaliador=_AVALIADOR,
                dados_entrada=dados_entrada,
            )
            tipo = dados.get("tipo", "entrada")
            ident = dados.get("identificacao") or {}
            endereco_slug = (ident.get("endereco") or "vistoria").replace(" ", "_")[:30]
            nome_arq = f"Laudo_Vistoria_{tipo.capitalize()}_{endereco_slug}.pdf"
            st.download_button(
                "📄 Baixar Laudo PDF",
                data=pdf_bytes,
                file_name=nome_arq,
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

    st.divider()
    with st.expander("⚖️ Embasamento legal"):
        st.write(PDFVIST.DISCLAIMER_VISTORIA)
        st.caption(
            "O laudo gerado pelo AvaliApp documenta o estado do imóvel para fins de locação. "
            "Recomenda-se coletar as assinaturas físicas das partes no ato da vistoria, "
            "ou utilizar uma plataforma de assinatura eletrônica certificada (ex.: ClickSign, ZapSign) "
            "para garantir validade jurídica plena."
        )

    st.divider()
    if st.button("← Voltar aos Cômodos", use_container_width=True):
        _ir_para(2)


# ── Roteamento ─────────────────────────────────────────────────────────────────
if passo_atual == 1:
    _render_passo_1()
elif passo_atual == 2:
    _render_passo_2()
elif passo_atual == 3:
    _render_passo_3()
