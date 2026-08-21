"""
AvaliApp — roteador/entrada (Streamlit `st.navigation`).

Centraliza: configuração da página, banco, login e navegação lateral.
Rodar localmente:
    cd "Avaliapp"
    streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from config import identidade as ID
from core import auth, db, supa, ui

st.set_page_config(
    page_title=ID.NOME_APP,
    page_icon="🏠",
    layout="wide",
)

ui.aplicar_estilo()

if not supa.configurado():
    st.error(
        "**AvaliApp ainda não está configurado.**\n\n"
        "Defina `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` em "
        "`.streamlit/secrets.toml` (desenvolvimento) ou no dashboard do "
        "Streamlit Cloud (produção). Veja `db/schema.sql` para criar a tabela "
        "e crie um bucket privado chamado `avaliapp-anexos` no Storage."
    )
    st.stop()

try:
    db.init_db()
except Exception as e:
    st.error(f"Não consegui conectar no banco: {e}")
    st.stop()

auth.require_login()

# Carrega perfil do usuário uma vez por sessão
if not st.session_state.get("perfil_carregado"):
    try:
        perfil = db.obter_perfil(st.session_state["user_id"])
        st.session_state["perfil"] = perfil or {}
    except Exception:
        st.session_state["perfil"] = {}
    st.session_state["perfil_carregado"] = True

# Logo na sidebar (SVG)
if Path(ID.LOGO_PATH).exists():
    st.logo(ID.LOGO_PATH)

paginas = [
    st.Page("pages/0_Inicio.py", title="Central",
            icon=":material/space_dashboard:", default=True),
    st.Page("pages/1_Nova_Avaliacao.py", title="Nova Avaliação",
            icon=":material/add_home_work:"),
    st.Page("pages/2_Historico.py", title="Histórico (Avaliações)",
            icon=":material/history:"),
    st.Page("pages/4_Vistoria.py", title="Nova Vistoria",
            icon=":material/home_search:"),
    st.Page("pages/5_Vistorias.py", title="Histórico (Vistorias)",
            icon=":material/fact_check:"),
    st.Page("pages/3_Perfil.py", title="Meu Perfil",
            icon=":material/manage_accounts:"),
]

with st.sidebar:
    st.divider()
    perfil = st.session_state.get("perfil", {})
    nome = perfil.get("nome") or st.session_state.get("user_email", "")
    creci = perfil.get("creci")
    st.caption(f"👤 {nome}")
    if creci:
        st.caption(f"CRECI: {creci}")
    elif perfil is not None:
        st.warning("Complete seu perfil para assinar PTAMs.", icon="⚠️")
    if st.button("Sair", use_container_width=True):
        auth.logout()
        st.rerun()

pg = st.navigation(paginas)
pg.run()
