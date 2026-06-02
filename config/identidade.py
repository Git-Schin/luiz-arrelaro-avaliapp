"""
Identidade visual do Avaliapp — marca real do Luiz Arrelaro.

Paleta extraída do logo oficial ("Logo - Luiz Arrelaro (sem fundo).png"):
preto + ciano (#06BFF2) sobre branco. Centralizado aqui para facilitar ajustes.

⚠️ Campos de CONTATO/CRECI ainda marcados como [PREENCHER] — completar com os
dados reais do Luiz (número do CRECI, telefone, e-mail, cidade/UF).
"""
from pathlib import Path

# --- Logo ---
# Logo oficial (preto + ciano, fundo transparente). Usado no app e nos PDFs.
LOGO_PATH = str(Path(__file__).resolve().parent.parent / "assets" / "logo_luiz.png")

# --- Nome e textos ---
NOME_APP = "Avaliapp"
TAGLINE = "Avaliação de imóveis com precisão e tecnologia"
EMPRESA = "Luiz Arrelaro — Consultor Imobiliário"

AVALIADOR = {
    "nome": "Luiz Gonzaga Arrelaro",
    "titulo": "Corretor de Imóveis · Consultor Imobiliário",
    "creci": "CRECI-SP 221.546-F",
    "cnai": "",                      # CNAI (Cadastro Nacional de Avaliadores) — preencher se houver
    "telefone": "+55 (11) 96909-2031",   # também WhatsApp
    "whatsapp": "+55 (11) 96909-2031",
    "email": "larrelaro@gmail.com",
    "cidade_uf": "Itatiba/SP",
}

# --- Paleta de cores (marca Luiz Arrelaro) ---
COR_PRIMARIA = "#0E0E10"        # preto da marca — confiança/sobriedade
COR_PRIMARIA_CLARA = "#26292E"
COR_ACENTO = "#06BFF2"          # ciano da marca — destaque
COR_SUCESSO = "#0A7EA4"         # ciano escuro — caixa de valor (bom contraste c/ branco)
COR_ALERTA = "#B23A3A"          # vermelho — ressalvas
COR_FUNDO = "#F4F7F9"           # cinza muito claro
COR_TEXTO = "#0E0E10"
COR_TEXTO_SUAVE = "#5A6675"

# Versão em RGB (0-255) para o gerador de PDF (fpdf2)
def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

RGB_PRIMARIA = _hex_to_rgb(COR_PRIMARIA)
RGB_ACENTO = _hex_to_rgb(COR_ACENTO)
RGB_SUCESSO = _hex_to_rgb(COR_SUCESSO)
RGB_TEXTO = _hex_to_rgb(COR_TEXTO)
RGB_TEXTO_SUAVE = _hex_to_rgb(COR_TEXTO_SUAVE)

# --- Rodapé legal padrão (aparece nos PDFs) ---
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
