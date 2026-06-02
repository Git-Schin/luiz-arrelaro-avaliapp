"""
Avaliapp — roteador/entrada (Streamlit `st.navigation`).

Centraliza: configuração da página, banco, login e a navegação lateral
(logo no topo via `st.logo`, ícones por opção). O conteúdo de cada tela fica
em `pages/`. Rodar localmente:
    cd "Avaliapp"
    streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from config import identidade as ID
from core import auth, db, supa, ui

st.set_page_config(
    page_title=f"{ID.NOME_APP} — {ID.EMPRESA}",
    page_icon="🏠",
    layout="wide",
)

ui.aplicar_estilo()  # CSS global da marca (vale para todas as páginas)

if not supa.configurado():
    st.error(
        "**Avaliapp ainda não está configurado.**\n\n"
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

auth.require_login()  # bloqueia tudo até autenticar

# Logo da marca no topo da sidebar, ACIMA do menu (st.logo posiciona automaticamente).
if Path(ID.LOGO_PATH).exists():
    st.logo(ID.LOGO_PATH, link="https://www.creci.org.br")

paginas = [
    st.Page("pages/0_Inicio.py", title="Central Avaliapp",
            icon=":material/space_dashboard:", default=True),
    st.Page("pages/1_Nova_Avaliacao.py", title="Nova Avaliação",
            icon=":material/add_home_work:"),
    st.Page("pages/2_Historico.py", title="Histórico",
            icon=":material/history:"),
]

with st.sidebar:
    st.divider()
    st.success("Conectado")
    if st.button("Sair", use_container_width=True):
        st.session_state["autenticado"] = False
        st.rerun()

pg = st.navigation(paginas)
pg.run()
