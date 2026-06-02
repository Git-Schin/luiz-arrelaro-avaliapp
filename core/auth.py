"""Login simples por senha (single-user). Multiusuário fica para depois."""
import streamlit as st

SENHA_PADRAO = "avaliapp"  # usada se não houver secrets.toml configurado


def _senha_correta() -> str:
    try:
        return st.secrets["app"]["senha"]
    except Exception:
        return SENHA_PADRAO


def require_login():
    """Bloqueia a página até a senha correta. Chamar no topo de cada página."""
    if st.session_state.get("autenticado"):
        return

    st.markdown("### 🔐 Avaliapp — acesso restrito")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", type="primary"):
        if senha == _senha_correta():
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.caption("Acesso individual. A senha pode ser definida em `.streamlit/secrets.toml`.")
    st.stop()
