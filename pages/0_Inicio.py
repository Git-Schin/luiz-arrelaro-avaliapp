"""Central Avaliapp — página inicial (dashboard e atalhos)."""
import streamlit as st

from config import identidade as ID
from core import db

st.markdown(f"### {ID.NOME_APP}")
st.caption(f"{ID.EMPRESA} · {ID.TAGLINE}")
st.markdown(
    f"<div style='height:4px;background:{ID.COR_ACENTO};border-radius:2px;margin:6px 0 10px;'></div>",
    unsafe_allow_html=True,
)

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Bem-vindo")
    st.write(
        "O **Avaliapp** apoia a elaboração de **Pareceres Técnicos de Avaliação "
        "Mercadológica (PTAM)** com o Método Comparativo Direto, geração de PDF e "
        "histórico das avaliações."
    )
    # Botão (e não link) para garantir o reset dos campos ao iniciar uma nova avaliação.
    if st.button("➕ Iniciar nova avaliação", type="primary"):
        st.session_state["_resetar_form"] = True
        st.switch_page("pages/1_Nova_Avaliacao.py")
    st.page_link("pages/2_Historico.py", label="📚 Ver histórico de avaliações", icon="🗂️")

with col2:
    avals = db.listar()
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
