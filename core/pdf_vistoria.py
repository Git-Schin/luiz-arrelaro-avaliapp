"""
Geração do Laudo de Vistoria de Imóvel para Locação.

Estrutura do PDF:
  1. Cabeçalho de identificação (imóvel + partes)
  2. Medidores e chaves entregues
  3. Cômodo a cômodo: tabela de itens (estado + obs) + fotos 2-up
  4. Comparativo entrada × saída (somente em vistorias de saída)
  5. Observações gerais
  6. Embasamento legal + disclaimer
  7. Página de assinatura (3 blocos: locatário · proprietário/imobiliária · vistoriador)
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from config import identidade as ID
from core.vistoria_tipos import ESTADOS, ESTADO_COR

_TRAD = str.maketrans({
    "—": "-", "–": "-", "•": "-", "“": '"', "”": '"',
    "‘": "'", "’": "'", "…": "...", " ": " ",
})

DISCLAIMER_VISTORIA = (
    "Este Laudo de Vistoria é elaborado em conformidade com a Lei nº 8.245, "
    "de 18 de outubro de 1991 (Lei do Inquilinato), artigos 22 e 23, que "
    "estabelecem as obrigações do locador e do locatário quanto à conservação "
    "do imóvel. Serve como instrumento de proteção às partes envolvidas na "
    "locação e pode ser anexado ao contrato de locação como prova do estado "
    "do imóvel na data da vistoria. A validade plena deste documento depende "
    "da assinatura de todos os presentes no ato da vistoria."
)


def _s(texto) -> str:
    if texto is None:
        return ""
    return str(texto).translate(_TRAD).encode("latin-1", "replace").decode("latin-1")


def _data_br(data_iso) -> str:
    if not data_iso:
        return ""
    try:
        return datetime.strptime(str(data_iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(data_iso)


class _PDF(FPDF):
    tipo_vistoria: str = "entrada"
    avaliador: dict

    def header(self):
        av = getattr(self, "avaliador", {}) or {}
        self.set_xy(self.l_margin, 7)
        self.set_text_color(*ID.RGB_PRIMARIA)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 6, _s(av.get("nome") or ID.NOME_APP), ln=1)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        creci = av.get("creci")
        sub = f"{av.get('titulo', '')} · {creci}" if creci else "Laudo de Vistoria"
        self.cell(0, 5, _s(sub), ln=1)
        self.set_fill_color(*ID.RGB_ACENTO)
        self.rect(0, 22, self.w, 1.2, "F")
        self.set_y(28)
        self.set_text_color(*ID.RGB_TEXTO)

    def footer(self):
        av = getattr(self, "avaliador", {}) or {}
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        nome = av.get("nome", "")
        rodape = f"{nome}  ·  {ID.NOME_APP}" if nome else ID.NOME_APP
        self.cell(0, 4, _s(rodape), align="L")
        self.cell(0, 4, _s(f"Página {self.page_no()}/{{nb}}"), align="R")

    def titulo_secao(self, texto: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ID.RGB_PRIMARIA)
        self.cell(0, 7, _s(texto), ln=1)
        self.set_draw_color(*ID.RGB_ACENTO)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_text_color(*ID.RGB_TEXTO)

    def par(self, texto: str, tamanho: int = 10, bold: bool = False):
        self.set_font("Helvetica", "B" if bold else "", tamanho)
        self.multi_cell(0, 5, _s(texto), ln=1)

    def campo(self, rotulo: str, valor: str, col_w: float | None = None):
        w = col_w or self.epw
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        self.cell(w, 5, _s(rotulo), ln=0)
        self.set_x(self.l_margin + w)  # reset x — cell(ln=0) can drift
        self.ln(0)
        # Reinicializa x
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        # Em vez de dois campos na mesma linha, fazemos em duas linhas para simplificar
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*ID.RGB_TEXTO)
        self.multi_cell(0, 5, _s(valor or "—"), ln=1)

    def linha_kv(self, rotulo: str, valor: str, w_rotulo: float = 50):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        self.cell(w_rotulo, 5, _s(rotulo + ":"), ln=0)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*ID.RGB_TEXTO)
        self.multi_cell(0, 5, _s(valor or "—"), ln=1)


# ── Seções individuais ────────────────────────────────────────────────────────

def _sec_identificacao(pdf: _PDF, dados: dict):
    ident = dados.get("identificacao") or {}
    tipo = dados.get("tipo", "entrada")
    tipo_label = "VISTORIA DE ENTRADA" if tipo == "entrada" else "VISTORIA DE SAÍDA"
    data_br = _data_br(ident.get("data_vistoria"))

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ID.RGB_PRIMARIA)
    pdf.cell(0, 8, _s(f"LAUDO DE {tipo_label}"), ln=1, align="C")
    if data_br:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
        pdf.cell(0, 6, _s(f"Data da vistoria: {data_br}"), ln=1, align="C")
    pdf.ln(3)
    pdf.set_text_color(*ID.RGB_TEXTO)

    pdf.titulo_secao("1. Imóvel Vistoriado")
    endereco = " ".join(filter(None, [
        ident.get("endereco"), ident.get("numero"),
    ]))
    pdf.linha_kv("Endereço", endereco)
    pdf.linha_kv("Bairro", ident.get("bairro"))
    pdf.linha_kv("Cidade/UF", ident.get("cidade_uf"))
    pdf.linha_kv("CEP", ident.get("cep"))
    pdf.ln(2)

    pdf.titulo_secao("2. Partes Envolvidas")
    loc_info = ident.get("locatario_nome", "")
    if ident.get("locatario_doc"):
        loc_info += f"  ·  CPF/RG: {ident['locatario_doc']}"
    pdf.linha_kv("Locatário", loc_info)

    prop_info = ident.get("proprietario_nome", "")
    if ident.get("proprietario_doc"):
        prop_info += f"  ·  CPF/CNPJ: {ident['proprietario_doc']}"
    pdf.linha_kv("Proprietário", prop_info)

    if ident.get("imobiliaria"):
        pdf.linha_kv("Imobiliária", ident.get("imobiliaria"))
    pdf.linha_kv("Vistoriador", ident.get("vistoriador_nome"))
    pdf.ln(2)


def _sec_medidores(pdf: _PDF, dados: dict):
    fech = dados.get("fechamento") or {}
    agua = fech.get("medidor_agua") or "—"
    luz = fech.get("medidor_luz") or "—"
    gas = fech.get("medidor_gas") or "—"
    chaves = str(fech.get("chaves_quantidade") or "—")

    pdf.titulo_secao("3. Medidores e Chaves")
    w = pdf.epw / 4
    # Cabeçalhos
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 244, 248)
    for lab in ["Medidor Água", "Medidor Luz", "Medidor Gás", "Chaves entregues"]:
        pdf.cell(w, 6, _s(lab), border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    for val in [agua, luz, gas, chaves]:
        pdf.cell(w, 7, _s(val), border=1, align="C")
    pdf.ln(5)

    # Fotos dos medidores (água, luz, gás)
    todas_fotos_med = []
    for key in ("fotos_agua", "fotos_luz", "fotos_gas"):
        todas_fotos_med.extend(fech.get(key) or [])
    _embed_fotos(pdf, todas_fotos_med)


def _estado_fill(estado: str) -> tuple[int, int, int]:
    cor = ESTADO_COR.get(estado, "#94A3B8")
    cor = cor.lstrip("#")
    r, g, b = int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16)
    # Versão mais clara (mistura 50% com branco)
    return (r + (255 - r) // 2, g + (255 - g) // 2, b + (255 - b) // 2)


def _tabela_itens(pdf: _PDF, itens: list[dict],
                  itens_entrada: list[dict] | None = None):
    """Tabela de itens: simples (entrada) ou comparativa (saída)."""
    comparativo = itens_entrada is not None
    pw = pdf.epw

    if comparativo:
        w_item, w_ent, w_sai, w_obs = pw * 0.28, pw * 0.14, pw * 0.14, pw * 0.44
        headers = ["Item", "Entrada", "Saída", "Observação (saída)"]
        widths = [w_item, w_ent, w_sai, w_obs]
    else:
        w_item, w_est, w_obs = pw * 0.30, pw * 0.20, pw * 0.50
        headers = ["Item", "Estado", "Observação"]
        widths = [w_item, w_est, w_obs]

    # Cabeçalho da tabela
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(27, 58, 107)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, _s(h), border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(*ID.RGB_TEXTO)

    for idx, item in enumerate(itens):
        nome = item.get("nome", "")
        estado = item.get("estado", "")
        obs = item.get("obs", "")
        fill_cor = _estado_fill(estado)
        fill_plain = (248, 250, 252) if idx % 2 == 0 else (255, 255, 255)

        if comparativo:
            # Acha o item correspondente na entrada
            e_item = next(
                (i for i in (itens_entrada or [])
                 if i.get("nome", "").lower() == nome.lower()),
                {}
            )
            e_estado = e_item.get("estado", "")
            e_fill = _estado_fill(e_estado)

            y0 = pdf.get_y()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_fill_color(*fill_plain)
            pdf.cell(w_item, 6, _s(nome), border=1, fill=True)
            pdf.set_fill_color(*e_fill)
            pdf.cell(w_ent, 6, _s(e_estado), border=1, fill=True, align="C")
            pdf.set_fill_color(*fill_cor)
            pdf.cell(w_sai, 6, _s(estado), border=1, fill=True, align="C")
            pdf.set_fill_color(*fill_plain)
            x_obs = pdf.get_x()
            pdf.multi_cell(w_obs, 6, _s(obs or ""), border=1, fill=True)
            pdf.set_y(max(pdf.get_y(), y0 + 6))
        else:
            y0 = pdf.get_y()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_fill_color(*fill_plain)
            pdf.cell(w_item, 6, _s(nome), border=1, fill=True)
            pdf.set_fill_color(*fill_cor)
            pdf.cell(w_est, 6, _s(estado), border=1, fill=True, align="C")
            pdf.set_fill_color(*fill_plain)
            x_obs = pdf.get_x()
            pdf.multi_cell(w_obs, 6, _s(obs or ""), border=1, fill=True)
            pdf.set_y(max(pdf.get_y(), y0 + 6))

    pdf.ln(2)


def _embed_fotos(pdf: _PDF, fotos: list[dict]):
    """Insere fotos em grade de 2 colunas."""
    fotos_ok = [f for f in fotos if f.get("bytes")]
    if not fotos_ok:
        return
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    pdf.cell(0, 5, _s(f"Fotos: {len(fotos_ok)} imagem(ns) registrada(s)"), ln=1)
    pdf.set_text_color(*ID.RGB_TEXTO)

    pw = pdf.epw
    img_w = (pw - 4) / 2
    img_h = img_w * 0.66

    for i, f in enumerate(fotos_ok):
        if i % 2 == 0:
            if i > 0:
                pdf.ln(2)
            x_start = pdf.l_margin
        else:
            x_start = pdf.l_margin + img_w + 4

        if pdf.get_y() + img_h > pdf.h - pdf.b_margin - 15:
            pdf.add_page()

        try:
            img_io = BytesIO(f["bytes"])
            pdf.image(img_io, x=x_start, y=pdf.get_y(), w=img_w, h=img_h,
                      keep_aspect_ratio=True)
        except Exception:
            pass

        if i % 2 == 1 or i == len(fotos_ok) - 1:
            pdf.set_y(pdf.get_y() + img_h + 2)

    pdf.ln(3)


def _sec_comodos(pdf: _PDF, dados: dict):
    comodos = dados.get("comodos") or []
    tipo = dados.get("tipo", "entrada")

    # Para saída: tenta carregar cômodos da entrada
    comodos_entrada: list[dict] | None = None
    if tipo == "saida":
        dados_entrada = dados.get("_entrada_dados") or {}
        comodos_entrada = dados_entrada.get("comodos") or []

    num_sec = 4
    for ci, comodo in enumerate(comodos):
        nome = comodo.get("nome", f"Cômodo {ci + 1}")
        icone = comodo.get("icone", "🏠")
        itens = comodo.get("itens") or []
        obs_geral = comodo.get("obs_geral", "")

        # Itens do cômodo correspondente na entrada (para comparativo)
        itens_ent: list[dict] | None = None
        if comodos_entrada is not None:
            comodo_ent = next(
                (c for c in comodos_entrada
                 if c.get("nome", "").lower() == nome.lower()),
                {}
            )
            itens_ent = comodo_ent.get("itens") or []

        pdf.titulo_secao(f"{num_sec}. {nome}")
        num_sec += 1

        if itens:
            _tabela_itens(pdf, itens, itens_ent)

        if obs_geral:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
            pdf.multi_cell(0, 5, _s(f"Obs.: {obs_geral}"), ln=1)
            pdf.set_text_color(*ID.RGB_TEXTO)

        # Fotos de todos os itens deste cômodo
        todas_fotos = []
        for item in itens:
            todas_fotos.extend(item.get("fotos") or [])
        _embed_fotos(pdf, todas_fotos)


def _sec_obs_gerais(pdf: _PDF, dados: dict, num_sec: int):
    obs = (dados.get("fechamento") or {}).get("obs_gerais", "")
    pdf.titulo_secao(f"{num_sec}. Observações Gerais")
    if obs:
        pdf.par(obs)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
        pdf.cell(0, 5, "Sem observações adicionais.", ln=1)
        pdf.set_text_color(*ID.RGB_TEXTO)
    pdf.ln(2)


def _sec_disclaimer(pdf: _PDF, num_sec: int):
    pdf.titulo_secao(f"{num_sec}. Embasamento Legal")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    pdf.multi_cell(0, 4.5, _s(DISCLAIMER_VISTORIA), ln=1)
    pdf.set_text_color(*ID.RGB_TEXTO)
    pdf.ln(2)


def _sec_assinatura(pdf: _PDF, dados: dict):
    """Página de assinatura com 3 blocos: locatário · proprietário/imob · vistoriador."""
    pdf.add_page()
    ident = dados.get("identificacao") or {}
    tipo = dados.get("tipo", "entrada")
    tipo_label = "ENTRADA" if tipo == "entrada" else "SAÍDA"

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*ID.RGB_PRIMARIA)
    pdf.cell(0, 8, "ACEITE E ASSINATURA DO LAUDO", ln=1, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    pdf.cell(0, 5, _s(
        f"Laudo de Vistoria de {tipo_label}  ·  "
        f"Imóvel: {ident.get('endereco', '')} {ident.get('numero', '')}  ·  "
        f"Data: {_data_br(ident.get('data_vistoria'))}"
    ), ln=1, align="C")
    pdf.ln(4)
    pdf.set_text_color(*ID.RGB_TEXTO)

    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 4.5, _s(
        "Declaro(amos) ter participado da vistoria do imóvel acima identificado, "
        "e que o estado registrado neste laudo corresponde ao verificado na data "
        "da inspeção, estando ciente(s) de seu conteúdo."
    ), ln=1)
    pdf.ln(4)

    partes = [
        ("LOCATÁRIO", ident.get("locatario_nome"), ident.get("locatario_doc")),
        (
            "PROPRIETÁRIO / IMOBILIÁRIA",
            ident.get("proprietario_nome") or ident.get("imobiliaria"),
            ident.get("proprietario_doc"),
        ),
        ("VISTORIADOR", ident.get("vistoriador_nome"), None),
    ]

    for label, nome, doc in partes:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*ID.RGB_PRIMARIA)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 6, f"  {_s(label)}", border=0, fill=True, ln=1)
        pdf.set_text_color(*ID.RGB_TEXTO)
        pdf.set_font("Helvetica", "", 9)
        pdf.ln(1)

        pdf.cell(40, 5, "Nome:", ln=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 5, _s(nome or ""), ln=1)
        pdf.set_font("Helvetica", "", 9)
        if doc:
            pdf.cell(40, 5, "CPF/RG/CNPJ:", ln=0)
            pdf.cell(0, 5, _s(doc), ln=1)

        pdf.ln(10)
        # Linha de assinatura
        x1 = pdf.l_margin
        x2 = pdf.l_margin + pdf.epw * 0.60
        y = pdf.get_y()
        pdf.set_draw_color(*ID.RGB_PRIMARIA)
        pdf.set_line_width(0.5)
        pdf.line(x1, y, x2, y)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
        pdf.cell(0, 4, "Assinatura", ln=1)
        pdf.set_text_color(*ID.RGB_TEXTO)

        # Data
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(40, 5, "Data:", ln=0)
        pdf.line(pdf.get_x(), pdf.get_y() + 4, pdf.get_x() + 50, pdf.get_y() + 4)
        pdf.ln(8)
        pdf.ln(4)

    # Gerado em
    pdf.set_y(-30)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    pdf.cell(0, 4, _s(
        f"Laudo gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} "
        f"pelo {ID.NOME_APP}. Validade legal condicionada às assinaturas acima."
    ), ln=1, align="C")


# ── Interface pública ─────────────────────────────────────────────────────────

def gerar_laudo(dados: dict, avaliador: dict | None = None,
                dados_entrada: dict | None = None) -> bytes:
    """Gera o Laudo de Vistoria em PDF e retorna os bytes.

    Args:
        dados: dict completo da vistoria (tipo, identificacao, comodos, fechamento).
        avaliador: perfil do usuário logado (nome, creci, titulo...).
        dados_entrada: dados da vistoria de entrada vinculada (para comparativo).
    """
    # Injeta dados da entrada para uso interno nas seções
    if dados_entrada:
        dados = dict(dados)
        dados["_entrada_dados"] = dados_entrada

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.avaliador = avaliador or {}
    pdf.alias_nb_pages()
    pdf.set_margins(left=15, top=30, right=15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    _sec_identificacao(pdf, dados)
    _sec_medidores(pdf, dados)
    _sec_comodos(pdf, dados)

    # Número dinâmico para observações (depende de quantos cômodos há)
    n_comodos = len(dados.get("comodos") or [])
    n_obs = 4 + n_comodos
    _sec_obs_gerais(pdf, dados, n_obs)
    _sec_disclaimer(pdf, n_obs + 1)
    _sec_assinatura(pdf, dados)

    return bytes(pdf.output())
