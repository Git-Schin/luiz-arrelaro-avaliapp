"""
Estilo visual central do AvaliApp (CSS injetado).

Chamado uma vez no `app.py`; o CSS vale para todas as páginas.
Paleta: Navy #1B3A6B + Emerald #10B981. Tipografia Inter.
"""
import streamlit as st

from config import identidade as ID

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Tipografia base */
[data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stHeader"] {{
    font-family: 'Inter', -apple-system, Segoe UI, Roboto, sans-serif;
}}

/* --- Logo na sidebar ---
   st.logo encolhe imagens; aqui ampliamos para boa leitura. */
img[data-testid="stLogo"] {{
    height: 2.8rem !important;
    width: auto !important;
    margin: 0.5rem auto 0.3rem !important;
    display: block;
}}

/* --- Sidebar ---------------------------------------------------------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #FFFFFF 0%, {ID.COR_FUNDO} 100%);
    border-right: 1px solid #E2E8F0;
}}
[data-testid="stSidebarNav"] a {{
    border-radius: 10px;
    margin: 2px 6px;
    transition: background .15s ease;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: rgba(27,58,107,0.08);
}}

/* --- Títulos ---------------------------------------------------------- */
h1, h2, h3 {{ letter-spacing: -0.01em; font-weight: 700; }}
h1 {{ color: {ID.COR_PRIMARIA}; }}

/* --- Botões ----------------------------------------------------------- */
.stButton > button, .stDownloadButton > button {{
    border-radius: 10px;
    font-weight: 600;
    transition: transform .12s ease, box-shadow .12s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(16,185,129,0.28);
}}

/* --- Métricas como card ----------------------------------------------- */
[data-testid="stMetric"] {{
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(27,58,107,0.05);
}}

/* --- Containers com borda (cards) ------------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}

/* --- Expanders -------------------------------------------------------- */
[data-testid="stExpander"] details {{
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    overflow: hidden;
}}

/* --- Selectbox / dropdown --------------------------------------------- */
div[data-baseweb="select"] > div {{
    border-radius: 10px;
    border-color: #CBD5E1;
}}
div[data-baseweb="popover"] ul,
div[data-baseweb="menu"] {{
    border-radius: 12px !important;
    padding: 4px !important;
    box-shadow: 0 8px 24px rgba(27,58,107,0.12) !important;
}}
div[data-baseweb="popover"] li,
div[data-baseweb="menu"] li {{
    border-radius: 8px;
    margin: 1px 2px;
    padding: 8px 10px;
}}
div[data-baseweb="popover"] li:hover,
div[data-baseweb="menu"] li:hover {{
    background: rgba(16,185,129,0.12) !important;
}}

/* --- Tabelas/data_editor --------------------------------------------- */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border-radius: 12px; }}

/* Reduz o respiro excessivo no topo da página principal */
.block-container {{ padding-top: 2.2rem; }}

/* --- Stepper do wizard ------------------------------------------------
   Pílulas dos passos via st.button; destaque do passo atual via type="primary". */
button[data-testid="stBaseButton-secondary"][kind="secondary"][key^="step_btn_"],
button[data-testid="stBaseButton-primary"][key^="step_btn_"] {{
    font-size: 0.92rem;
    padding: 0.55rem 0.6rem;
}}
button[key^="step_btn_"] p {{
    text-align: center;
    margin: 0;
}}

/* ═══════════════════════════════════════════════════════════════════════
   RESPONSIVO — MOBILE (≤ 768 px)
   ═══════════════════════════════════════════════════════════════════════ */
@media screen and (max-width: 768px) {{

    /* Padding da página menor */
    .block-container {{
        padding-top: 1rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }}

    /* Colunas colapsam para coluna única */
    [data-testid="stHorizontalBlock"] {{
        flex-wrap: wrap !important;
    }}
    [data-testid="stColumn"] {{
        width: 100% !important;
        flex: 0 0 100% !important;
        min-width: 100% !important;
    }}

    /* Botões maiores — área de toque adequada */
    .stButton > button,
    .stDownloadButton > button {{
        min-height: 3rem !important;
        font-size: 1rem !important;
        padding: 0.5rem 0.75rem !important;
        border-radius: 12px !important;
    }}

    /* Selects e inputs maiores */
    [data-baseweb="select"] span,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {{
        font-size: 1rem !important;
    }}

    /* Títulos menores para caber na tela */
    h1 {{ font-size: 1.5rem !important; }}
    h2 {{ font-size: 1.2rem !important; }}
    h3 {{ font-size: 1.05rem !important; }}

    /* Camera input ocupa toda a largura */
    [data-testid="stCameraInput"] {{
        width: 100% !important;
    }}
    [data-testid="stCameraInput"] > div {{
        width: 100% !important;
    }}

    /* Sidebar ocupa largura razoável ao abrir */
    [data-testid="stSidebar"] {{
        min-width: 80vw !important;
    }}

    /* Tabelas com scroll horizontal */
    [data-testid="stDataFrame"],
    [data-testid="stDataEditor"] {{
        overflow-x: auto !important;
    }}

    /* Esconde o texto longo nos botões do stepper no mobile */
    button[key^="step_"] p {{
        font-size: 0.8rem !important;
    }}
}}
</style>
"""


def detectar_mobile() -> bool:
    """Detecta dispositivo móvel via User-Agent. Retorna True para mobile/tablet."""
    try:
        ua = st.context.headers.get("User-Agent", "")
        return any(m in ua.lower() for m in ("mobile", "android", "iphone", "ipad", "tablet"))
    except Exception:
        return False


def aplicar_estilo() -> None:
    """Injeta o CSS global da marca. Chamar uma vez no roteador (app.py)."""
    st.markdown(_CSS, unsafe_allow_html=True)
