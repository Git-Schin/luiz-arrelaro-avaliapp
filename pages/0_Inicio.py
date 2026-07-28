"""Central AvaliApp — página inicial (dashboard e atalhos)."""
import streamlit as st

from config import identidade as ID
from core import db

perfil = st.session_state.get("perfil", {})
nome = perfil.get("nome") or st.session_state.get("user_email", "Usuário")

st.markdown(f"### {ID.NOME_APP}")
st.caption(ID.TAGLINE)
st.markdown(
    f"<div style='height:4px;background:{ID.COR_ACENTO};border-radius:2px;margin:6px 0 10px;'></div>",
    unsafe_allow_html=True,
)

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader(f"Bem-vindo, {nome.split('@')[0]}!")
    st.write(
        "O **AvaliApp** apoia a elaboração de **Pareceres Técnicos de Avaliação "
        "Mercadológica (PTAM)** com o Método Comparativo Direto, geração de PDF e "
        "histórico das avaliações."
    )
    if st.button("➕ Iniciar nova avaliação", type="primary"):
        st.session_state["_resetar_form"] = True
        st.switch_page("pages/1_Nova_Avaliacao.py")
    st.page_link("pages/2_Historico.py", label="📚 Ver histórico de avaliações", icon="🗂️")

with col2:
    user_id = st.session_state.get("user_id")
    avals = db.listar(user_id=user_id)
    st.metric("Avaliações no histórico", len(avals))
    if avals:
        ultima = avals[0]
        st.caption(f"Última: {ultima['endereco'] or ultima['solicitante'] or '—'}")

st.divider()
with st.expander("⚖️ Aviso legal e metodologia"):
    st.write(ID.DISCLAIMER_LEGAL)
    st.caption(
        "Método Comparativo Direto de Dados de Mercado (tratamento por fatores), "
        "metodologia ABNT NBR 14653. Os parâmetros (graus, fatores) devem ser "
        "validados contra o texto oficial da norma antes de uso profissional."
    )
