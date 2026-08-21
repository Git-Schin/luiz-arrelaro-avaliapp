"""Histórico de vistorias — listar, baixar laudo PDF, excluir."""
import streamlit as st

from core import vistoria_db as VDB, vistoria_anexos as VAN
from core import pdf_vistoria as PDFVIST

_USER_ID = st.session_state.get("user_id")
_AVALIADOR = st.session_state.get("perfil", {})

st.title("📋 Histórico de Vistorias")

# ── Filtros ───────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([3, 1, 1])
busca = c1.text_input("🔎 Buscar por endereço, locatário ou cidade")
filtro_tipo = c2.selectbox("Tipo", ["Todos", "🔑 Entrada", "🏁 Saída"])
filtro_status = c3.selectbox("Status", ["Todos", "🟡 Rascunhos", "✅ Concluídas"])

tipo_db = None
if "Entrada" in filtro_tipo:
    tipo_db = VDB.TIPO_ENTRADA
elif "Saída" in filtro_tipo:
    tipo_db = VDB.TIPO_SAIDA

status_db = None
if "Rascunhos" in filtro_status:
    status_db = VDB.STATUS_RASCUNHO
elif "Concluídas" in filtro_status:
    status_db = VDB.STATUS_CONCLUIDO

try:
    vistorias = VDB.listar(user_id=_USER_ID, busca=busca,
                            status=status_db, tipo=tipo_db)
except Exception as e:
    st.error(f"Erro ao carregar vistorias: {e}")
    vistorias = []

if not vistorias:
    st.info("Nenhuma vistoria encontrada. Crie uma nova na página **Nova Vistoria**.")
    st.stop()

st.caption(f"{len(vistorias)} vistoria(s).")

# ── Lista ─────────────────────────────────────────────────────────────────────
for v in vistorias:
    is_rasc = (v.get("status") or VDB.STATUS_CONCLUIDO) == VDB.STATUS_RASCUNHO
    tipo_label = "🔑 Entrada" if v.get("tipo") == VDB.TIPO_ENTRADA else "🏁 Saída"
    badge = "🟡 Rascunho" if is_rasc else "✅ Concluída"
    titulo_card = (
        f"{badge} · {tipo_label} · #{v['id']} · "
        f"{v.get('endereco') or '—'} · "
        f"{v.get('locatario_nome') or '—'}"
    )

    with st.expander(titulo_card):
        st.write(
            f"**Cidade/UF:** {v.get('cidade_uf') or '—'}  ·  "
            f"**Data:** {v.get('data_vistoria') or '—'}  ·  "
            f"**Tipo:** {tipo_label}  \n"
            f"**Criada:** {v.get('criado_em', '')[:16]}  ·  "
            f"**Atualizada:** {v.get('atualizado_em', '')[:16]}"
        )

        c_edit, c_pdf, c_del = st.columns(3)

        with c_edit:
            lbl = "▶️ Retomar rascunho" if is_rasc else "✏️ Abrir / revisar"
            if st.button(lbl, key=f"edit_{v['id']}"):
                row = VDB.obter(v["id"], user_id=_USER_ID)
                if row:
                    dados_vis = dict(row.get("dados") or {})
                    # Baixa fotos do Storage para bytes (para PDF e exibição)
                    try:
                        comodos_com_bytes = VAN.carregar_fotos_vistoria(
                            dados_vis.get("comodos") or []
                        )
                        dados_vis["comodos"] = comodos_com_bytes
                    except Exception:
                        pass
                    st.session_state["vistoria"] = dados_vis
                    st.session_state["vistoria_id"] = v["id"]
                    st.session_state["vistoria_passo"] = 1
                    st.session_state.pop("vistoria_comodo_idx", None)
                    st.session_state.pop("vistoria_entrada_dados", None)
                    st.switch_page("pages/4_Vistoria.py")

        with c_pdf:
            pdf_disabled = is_rasc
            if not pdf_disabled:
                try:
                    row = VDB.obter(v["id"], user_id=_USER_ID)
                    dados_vis = dict((row or {}).get("dados") or {})
                    try:
                        comodos_bytes = VAN.carregar_fotos_vistoria(
                            dados_vis.get("comodos") or []
                        )
                        dados_vis["comodos"] = comodos_bytes
                    except Exception:
                        pass

                    # Carrega dados da entrada se for saída
                    dados_ent = None
                    eid = dados_vis.get("vistoria_entrada_id")
                    if eid:
                        try:
                            row_ent = VDB.obter(eid, user_id=_USER_ID)
                            dados_ent = (row_ent or {}).get("dados")
                        except Exception:
                            pass

                    pdf_bytes = PDFVIST.gerar_laudo(
                        dados_vis, avaliador=_AVALIADOR, dados_entrada=dados_ent
                    )
                    tipo_str = dados_vis.get("tipo", "vistoria")
                    nome_arq = f"Laudo_Vistoria_{tipo_str.capitalize()}_{v['id']}.pdf"
                    st.download_button(
                        "📄 Laudo PDF",
                        data=pdf_bytes,
                        file_name=nome_arq,
                        mime="application/pdf",
                        key=f"pdf_{v['id']}",
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")
            else:
                st.button("📄 Laudo PDF", disabled=True, key=f"pdf_{v['id']}",
                          help="Disponível somente após finalizar a vistoria.")

        with c_del:
            if st.button("🗑️ Excluir", key=f"del_{v['id']}"):
                try:
                    VDB.excluir(v["id"], user_id=_USER_ID)
                    VAN.excluir(v["id"])
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")
