"""Histórico — banco de avaliações: buscar/filtrar, reabrir/atualizar, baixar PDF, excluir."""
import streamlit as st

from core import anexos as AN, db
from core.calculo import formatar_brl
from core import pdf as PDFGEN

_USER_ID = st.session_state.get("user_id")
_AVALIADOR = st.session_state.get("perfil", {})

st.title("📚 Histórico de avaliações")

c1, c2 = st.columns([3, 1])
busca = c1.text_input("🔎 Buscar por solicitante, endereço ou cidade")
filtro_status = c2.selectbox("Status",
                              ["Todos", "🟡 Rascunhos", "✅ Concluídos"],
                              index=0)
status_db = None
if filtro_status.endswith("Rascunhos"):
    status_db = db.STATUS_RASCUNHO
elif filtro_status.endswith("Concluídos"):
    status_db = db.STATUS_CONCLUIDO

avals = db.listar(user_id=_USER_ID, busca=busca, status=status_db)

if not avals:
    st.info("Nenhuma avaliação encontrada. Crie uma na página **Nova Avaliação**.")
    st.stop()

st.caption(f"{len(avals)} avaliação(ões).")

for a in avals:
    titulo = a["endereco"] or a["solicitante"] or f"Avaliação #{a['id']}"
    is_rasc = (a.get("status") or db.STATUS_CONCLUIDO) == db.STATUS_RASCUNHO
    badge = "🟡 Rascunho" if is_rasc else "✅ Concluída"
    valor_txt = "—" if is_rasc else formatar_brl(a["valor_total"])
    with st.expander(f"{badge} · #{a['id']} · {titulo} · {valor_txt}"):
        st.write(
            f"**Tipo:** {a['tipo_imovel'] or '—'}  ·  **Solicitante:** {a['solicitante'] or '—'}  \n"
            f"**Cidade/UF:** {a['cidade_uf'] or '—'}  ·  **Grau:** {a['grau'] or '—'}  \n"
            f"**Criado:** {a['criado_em']}  ·  **Atualizado:** {a['atualizado_em']}"
            + (f"  ·  **Passo:** {a.get('passo_atual') or 1}/5" if is_rasc else "")
        )
        registro = db.obter(a["id"], user_id=_USER_ID)
        dados = registro["dados"]
        fotos = AN.carregar_fotos(dados.get("fotos_imovel"))

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            label = "▶️ Retomar rascunho" if is_rasc else "✏️ Abrir / atualizar"
            if st.button(label, key=f"edit_{a['id']}"):
                dados["_passo_atual"] = a.get("passo_atual") or 1
                st.session_state["edicao"] = dados
                st.session_state["edicao_id"] = a["id"]
                st.session_state["fotos_imovel"] = fotos
                st.session_state.pop("ultimo_resultado", None)
                st.session_state.pop("ultimo_resultado_obj", None)
                st.session_state.pop("_edic_hidratado", None)
                st.session_state.pop("wizard_passo", None)
                st.session_state.pop("_comp_base_carregado", None)
                st.switch_page("pages/1_Nova_Avaliacao.py")
        with c2:
            st.download_button("📄 PTAM",
                               data=PDFGEN.gerar_ptam(dados, fotos=fotos, avaliador=_AVALIADOR),
                               file_name=f"PTAM_{a['id']}.pdf", mime="application/pdf",
                               key=f"ptam_{a['id']}", disabled=is_rasc,
                               help="Indisponível para rascunhos" if is_rasc else None)
        with c3:
            st.download_button("🎯 Apresentação",
                               data=PDFGEN.gerar_apresentacao(dados, fotos=fotos,
                                                              avaliador=_AVALIADOR),
                               file_name=f"Apresentacao_{a['id']}.pdf",
                               mime="application/pdf",
                               key=f"apr_{a['id']}", disabled=is_rasc,
                               help="Indisponível para rascunhos" if is_rasc else None)
        with c4:
            if st.button("🗑️ Excluir", key=f"del_{a['id']}"):
                db.excluir(a["id"], user_id=_USER_ID)
                AN.excluir(a["id"])
                st.rerun()
