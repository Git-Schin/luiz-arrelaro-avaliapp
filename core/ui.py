"""
Estilo visual central do Avaliapp (CSS injetado).

Chamado uma vez no `app.py` (roteador); como o Streamlit é uma SPA, o CSS vale
para todas as páginas. Mantém a marca (ciano #06BFF2 + preto) e dá um acabamento
mais moderno: tipografia Inter, cards, botões, métricas, sidebar e dropdowns.

⚠️ Evita o seletor universal `*` para não sobrescrever a fonte dos ícones
Material usados no menu (eles têm font-family própria).
"""
import streamlit as st

from config import identidade as ID

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Tipografia base (containers herdam; ícones Material mantêm a fonte própria) */
[data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stHeader"] {{
    font-family: 'Inter', -apple-system, Segoe UI, Roboto, sans-serif;
}}

/* --- Logo no topo da sidebar ---------------------------------------------
   st.logo encolhe logos quadrados a ~24px; aqui ampliamos para boa leitura. */
img[data-testid="stLogo"] {{
    height: 3.4rem !important;
    width: auto !important;
    margin: 0.5rem auto 0.3rem !important;
    display: block;
}}

/* --- Sidebar -------------------------------------------------------------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #FFFFFF 0%, {ID.COR_FUNDO} 100%);
    border-right: 1px solid #E6EBEF;
}}
/* Itens do menu de navegação */
[data-testid="stSidebarNav"] a {{
    border-radius: 10px;
    margin: 2px 6px;
    transition: background .15s ease;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: rgba(6,191,242,0.10);
}}

/* --- Títulos -------------------------------------------------------------- */
h1, h2, h3 {{ letter-spacing: -0.01em; font-weight: 700; }}
h1 {{ color: {ID.COR_PRIMARIA}; }}

/* --- Botões --------------------------------------------------------------- */
.stButton > button, .stDownloadButton > button {{
    border-radius: 10px;
    font-weight: 600;
    transition: transform .12s ease, box-shadow .12s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(6,191,242,0.28);
}}

/* --- Métricas como card --------------------------------------------------- */
[data-testid="stMetric"] {{
    background: #FFFFFF;
    border: 1px solid #E6EBEF;
    border-radius: 14px;
    padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(14,14,16,0.05);
}}

/* --- Containers com borda (cards) ---------------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}

/* --- Expanders ------------------------------------------------------------ */
[data-testid="stExpander"] details {{
    border-radius: 12px;
    border: 1px solid #E6EBEF;
    overflow: hidden;
}}

/* --- Selectbox / dropdown ------------------------------------------------- */
div[data-baseweb="select"] > div {{
    border-radius: 10px;
    border-color: #D6DEE4;
}}
/* Menu aberto: cantos, espaçamento e realce no hover/seleção */
div[data-baseweb="popover"] ul,
div[data-baseweb="menu"] {{
    border-radius: 12px !important;
    padding: 4px !important;
    box-shadow: 0 8px 24px rgba(14,14,16,0.12) !important;
}}
div[data-baseweb="popover"] li,
div[data-baseweb="menu"] li {{
    border-radius: 8px;
    margin: 1px 2px;
    padding: 8px 10px;
}}
div[data-baseweb="popover"] li:hover,
div[data-baseweb="menu"] li:hover {{
    background: rgba(6,191,242,0.12) !important;
}}

/* --- Tabelas/data_editor: cantos arredondados ----------------------------- */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border-radius: 12px; }}

/* Reduz o respiro excessivo no topo da página principal */
.block-container {{ padding-top: 2.2rem; }}

/* --- Stepper do wizard de Nova Avaliação ---------------------------------
   As pílulas dos passos são `st.button` numa linha de colunas. Aqui só fazemos
   ajustes de respiro/tipografia; o destaque do passo atual vem do `type="primary"`
   nativo do Streamlit (que herda a cor da marca em config.toml). */
button[data-testid="stBaseButton-secondary"][kind="secondary"][key^="step_btn_"],
button[data-testid="stBaseButton-primary"][key^="step_btn_"] {{
    font-size: 0.92rem;
    padding: 0.55rem 0.6rem;
}}
/* Texto centralizado nas pílulas */
button[key^="step_btn_"] p {{
    text-align: center;
    margin: 0;
}}
</style>
"""


def aplicar_estilo() -> None:
    """Injeta o CSS global da marca. Chamar uma vez no roteador (app.py)."""
    st.markdown(_CSS, unsafe_allow_html=True)
