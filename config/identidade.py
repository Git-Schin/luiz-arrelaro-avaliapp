"""
Identidade visual do AvaliApp — produto SaaS de avaliação de imóveis.

Paleta: Navy #1B3A6B (confiança, autoridade) + Emerald #10B981 (precisão, crescimento).
Dados do avaliador (nome, CRECI, contato) ficam no perfil do usuário (tabela `perfis`),
não aqui — cada assinante tem suas próprias credenciais.
"""
from pathlib import Path

# --- Logo ---
LOGO_PATH = str(Path(__file__).resolve().parent.parent / "assets" / "logo_avaliapp.svg")

# --- Nome e textos ---
NOME_APP = "AvaliApp"
TAGLINE = "Avaliação de imóveis com precisão e tecnologia"
EMPRESA = "AvaliApp"

# --- Paleta de cores ---
COR_PRIMARIA = "#1B3A6B"        # navy — confiança/autoridade
COR_PRIMARIA_CLARA = "#2D4E8A"
COR_ACENTO = "#10B981"          # emerald — precisão/crescimento
COR_SUCESSO = "#059669"         # emerald escuro — caixa de valor
COR_ALERTA = "#DC2626"          # vermelho — ressalvas
COR_FUNDO = "#F0F4F8"           # cinza azulado claro
COR_TEXTO = "#1E293B"           # slate-800
COR_TEXTO_SUAVE = "#64748B"     # slate-500


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


RGB_PRIMARIA = _hex_to_rgb(COR_PRIMARIA)
RGB_ACENTO = _hex_to_rgb(COR_ACENTO)
RGB_SUCESSO = _hex_to_rgb(COR_SUCESSO)
RGB_TEXTO = _hex_to_rgb(COR_TEXTO)
RGB_TEXTO_SUAVE = _hex_to_rgb(COR_TEXTO_SUAVE)

# --- Rodapé legal padrão (PDFs) ---
DISCLAIMER_LEGAL = (
    "Este documento é um Parecer Técnico de Avaliação Mercadológica (PTAM), "
    "elaborado por Corretor de Imóveis inscrito no CRECI, com fundamento na "
    "Lei nº 6.530/1978 e na Resolução COFECI nº 1.066/2007, utilizando a "
    "metodologia da ABNT NBR 14653. NÃO constitui laudo de avaliação de engenharia "
    "nem Anotação de Responsabilidade Técnica (ART), de atribuição exclusiva de "
    "engenheiros e arquitetos (CREA/CAU). Trata-se de parecer de natureza mercadológica, "
    "destinado a subsidiar negociações e decisões, e não substitui avaliação judicial "
    "ou bancária quando esta for legalmente exigida."
)
