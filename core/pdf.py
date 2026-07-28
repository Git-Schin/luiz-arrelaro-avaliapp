"""
Geração de PDF: PTAM completo (técnico) e Apresentação (resumida ao cliente).

Usa fpdf2 com fonte core (Helvetica), que cobre os acentos do português via
latin-1. Caracteres fora do latin-1 são sanitizados.

`gerar_ptam` e `gerar_apresentacao` recebem `avaliador` como parâmetro —
dict com nome, titulo, creci, cnai, telefone, whatsapp, email_contato, cidade_uf.
Em contexto multi-usuário, vem do perfil do usuário logado.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from config import identidade as ID
from core.calculo import formatar_brl

_AVALIADOR_VAZIO: dict = {}

# Pontuação tipográfica que o latin-1 não cobre → equivalente ASCII
_TRAD_PONTUACAO = str.maketrans({
    "—": "-", "–": "-", "•": "-", "“": '"', "”": '"',
    "‘": "'", "’": "'", "…": "...", " ": " ",
})


def _s(texto) -> str:
    if texto is None:
        return ""
    return str(texto).translate(_TRAD_PONTUACAO).encode("latin-1", "replace").decode("latin-1")


def _so_preenchidos(*valores) -> list[str]:
    return [v for v in valores if v and "[PREENCHER]" not in str(v)]


class _BasePDF(FPDF):
    titulo_doc = "DOCUMENTO"
    avaliador: dict = _AVALIADOR_VAZIO

    def header(self):
        av = self.avaliador or {}
        self.set_xy(self.l_margin, 7)
        self.set_text_color(*ID.RGB_PRIMARIA)
        self.set_font("Helvetica", "B", 13)
        nome_av = av.get("nome") or ID.NOME_APP
        self.cell(0, 6, _s(nome_av), ln=1)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        creci = av.get("creci")
        subtitulo = f"{av.get('titulo', '')} · {creci}" if creci else self.titulo_doc
        self.cell(0, 5, _s(subtitulo), ln=1)
        # Linha de acento (emerald da marca)
        self.set_fill_color(*ID.RGB_ACENTO)
        self.rect(0, 22, self.w, 1.2, "F")
        self.set_y(28)
        self.set_text_color(*ID.RGB_TEXTO)

    def footer(self):
        av = self.avaliador or {}
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*ID.RGB_TEXTO_SUAVE)
        nome = av.get("nome", "")
        creci = av.get("creci", "")
        rodape = f"{nome} - {creci}  ·  gerado com {ID.NOME_APP}" if nome else f"gerado com {ID.NOME_APP}"
        self.cell(0, 4, _s(rodape), align="L")
        self.cell(0, 4, _s(f"Página {self.page_no()}/{{nb}}"), align="R")

    def titulo_secao(self, texto):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ID.RGB_PRIMARIA)
        self.cell(0, 7, _s(texto), ln=1)
        self.set_draw_color(*ID.RGB_ACENTO)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_text_color(*ID.RGB_TEXTO)
        self.set_font("Helvetica", "", 10)

    def par(self, texto):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*ID.RGB_TEXTO)
        self.multi_cell(0, 5, _s(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def linha_dado(self, rotulo, valor):
        if valor in (None, "", 0):
            return
        self.set_font("Helvetica", "B", 10)
        self.cell(55, 6, _s(rotulo), border=0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, _s(valor), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _galeria_fotos(pdf, fotos, altura_max=60):
    """Renderiza fotos em 2 colunas preservando proporção."""
    fotos = [f for f in (fotos or []) if f.get("bytes")]
    if not fotos:
        return
    larg = (pdf.w - pdf.l_margin - pdf.r_margin - 6) / 2

    def _dim(b):
        try:
            from PIL import Image
            w_px, h_px = Image.open(BytesIO(b)).size
            w, h = larg, larg * h_px / w_px
            if h > altura_max:
                w, h = larg * altura_max / h, altura_max
            return w, h
        except Exception:
            return larg, altura_max

    fila = []

    def _flush():
        if not fila:
            return
        hmax = min(max(h for _, _, h in fila), altura_max)
        if pdf.get_y() + hmax > pdf.h - 18:
            pdf.add_page()
        y = pdf.get_y()
        for i, (b, w, h) in enumerate(fila):
            x = pdf.l_margin + i * (larg + 6)
            pdf.image(BytesIO(b), x=x, y=y, w=w, h=h)
        pdf.set_y(y + hmax + 4)
        fila.clear()

    for f in fotos:
        w, h = _dim(f["bytes"])
        fila.append((f["bytes"], w, h))
        if len(fila) == 2:
            _flush()
    _flush()


def _cabecalho_imovel(pdf, dados):
    imovel = dados.get("imovel", {})
    pdf.linha_dado("Solicitante:", imovel.get("solicitante"))
    pdf.linha_dado("Finalidade:", imovel.get("finalidade"))
    pdf.linha_dado("Endereço:", imovel.get("endereco"))
    pdf.linha_dado("Bairro:", imovel.get("bairro"))
    pdf.linha_dado("Cidade/UF:", imovel.get("cidade_uf"))
    pdf.linha_dado("Matrícula:", imovel.get("matricula"))
    pdf.linha_dado("Inscrição IPTU:", imovel.get("inscricao_iptu"))


def gerar_ptam(dados: dict, fotos: list[dict] | None = None,
               avaliador: dict | None = None) -> bytes:
    """Gera o PTAM completo (técnico)."""
    av = avaliador or {}
    pdf = _BasePDF()
    pdf.avaliador = av
    pdf.titulo_doc = "Parecer Técnico de Avaliação Mercadológica (PTAM)"
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    resultado = dados.get("resultado", {})
    imovel = dados.get("imovel", {})
    tipo = dados.get("tipo_rotulo", dados.get("tipo_imovel", ""))
    textos_ia = dados.get("textos_ia", {})

    pdf.titulo_secao("1. Objeto e finalidade")
    pdf.par(f"Avaliação do valor de mercado do imóvel do tipo {tipo}, "
            f"para fins de {imovel.get('finalidade', '-')}, conforme dados a seguir.")
    _cabecalho_imovel(pdf, dados)

    pdf.titulo_secao("2. Pressupostos e ressalvas")
    if textos_ia.get("pressupostos"):
        pdf.par(textos_ia["pressupostos"])
    else:
        pdf.par("Avaliação baseada nas informações e documentos fornecidos pelo solicitante "
                "e em pesquisa de mercado. Pressupõe-se a veracidade da documentação e a "
                "inexistência de ônus ocultos não informados. Vistoria conforme registrado. "
                "Eventuais condições limitantes específicas estão indicadas pelo avaliador.")

    pdf.titulo_secao("3. Caracterização do imóvel")
    if textos_ia.get("descricao_imovel"):
        pdf.par(textos_ia["descricao_imovel"])
    for grupo in dados.get("imovel_detalhado", []):
        for rotulo, valor in grupo:
            pdf.linha_dado(f"{rotulo}:", valor)
    if fotos:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ID.RGB_PRIMARIA)
        pdf.cell(0, 6, _s("Registro fotográfico"), ln=1)
        pdf.set_text_color(*ID.RGB_TEXTO)
        _galeria_fotos(pdf, fotos)

    pdf.titulo_secao("4. Metodologia")
    pdf.par("Adotado o Método Comparativo Direto de Dados de Mercado, com tratamento por "
            "fatores de homogeneização, em conformidade com a metodologia da ABNT NBR 14653 "
            "(partes 1 e 2). Os dados de mercado foram homogeneizados à condição do imóvel "
            "avaliando e saneados estatisticamente.")

    pdf.titulo_secao("5. Pesquisa de mercado e homogeneização")
    _tabela_comparaveis(pdf, dados.get("comparaveis", []))
    if textos_ia.get("comentario_mercado"):
        pdf.ln(2)
        pdf.par(textos_ia["comentario_mercado"])

    pdf.titulo_secao("6. Conclusão de valor")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*ID.RGB_SUCESSO)
    pdf.cell(0, 8, _s(f"Valor de mercado: {formatar_brl(resultado.get('valor_total'))}"), ln=1)
    pdf.set_text_color(*ID.RGB_TEXTO)
    pdf.set_font("Helvetica", "", 10)
    if resultado.get("valor_unitario_medio"):
        pdf.linha_dado("Valor unitário:", f"{formatar_brl(resultado['valor_unitario_medio'])}/m²")
    pdf.linha_dado("Intervalo (campo de arbítrio ±15%):",
                   f"{formatar_brl(resultado.get('valor_min_arbitrio'))} a "
                   f"{formatar_brl(resultado.get('valor_max_arbitrio'))}")
    pdf.linha_dado("Comparáveis utilizados:", str(resultado.get("n_comparaveis_usados", 0)))
    grau_txt = resultado.get("grau_fundamentacao") or "—"
    if resultado.get("grau_pontos"):
        grau_txt += f" ({resultado['grau_pontos']}/12 pontos, NBR 14653-2)"
    pdf.linha_dado("Grau de fundamentação:", grau_txt)
    graus_itens = resultado.get("graus_itens") or {}
    if graus_itens:
        rotulos = {
            "1_caracterizacao": "Caracterização", "2_quantidade": "Qtd. dados",
            "3_identificacao": "Identif. dados", "4_conjunto_fatores": "Conjunto fatores",
        }
        detalhe = "; ".join(f"{rotulos.get(k, k)}: {v}" for k, v in graus_itens.items())
        pdf.linha_dado("Itens da fundamentação:", detalhe)
    pdf.linha_dado("Data de referência:", datetime.now().strftime("%d/%m/%Y"))
    if textos_ia.get("justificativa_valor"):
        pdf.ln(2)
        pdf.par(textos_ia["justificativa_valor"])

    pdf.titulo_secao("7. Assinatura")
    pdf.ln(8)
    pdf.cell(0, 5, _s("_" * 45), ln=1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, _s(av.get("nome", "")), ln=1)
    pdf.set_font("Helvetica", "", 9)
    titulo = av.get("titulo", "Corretor de Imóveis")
    creci = av.get("creci", "")
    if titulo or creci:
        pdf.cell(0, 5, _s(f"{titulo} - {creci}" if creci else titulo), ln=1)
    if av.get("cnai"):
        pdf.cell(0, 5, _s(f"CNAI: {av['cnai']}"), ln=1)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    pdf.multi_cell(0, 3.5, _s(ID.DISCLAIMER_LEGAL), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


def _tabela_comparaveis(pdf, comparaveis):
    usados = [c for c in comparaveis if c.get("incluir")]
    if not usados:
        pdf.par("Nenhum comparável incluído.")
        return
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*ID.RGB_PRIMARIA)
    pdf.set_text_color(255, 255, 255)
    larguras = [58, 24, 22, 22, 22, 22]
    cab = ["Comparável / Fonte", "Preço", "Área(m²)", "R$/m²", "Fator", "Homog."]
    for w, t in zip(larguras, cab):
        pdf.cell(w, 6, _s(t), border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(*ID.RGB_TEXTO)
    pdf.set_font("Helvetica", "", 8)
    for c in usados:
        valido = c.get("valido", True)
        if not valido:
            pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
        desc = (c.get("descricao") or c.get("fonte") or "-")[:34]
        if not valido:
            desc += " (descartado)"
        vals = [
            desc,
            formatar_brl(c.get("preco_total")).replace("R$ ", ""),
            f"{c.get('area', 0):.0f}",
            formatar_brl(c.get("valor_unitario")).replace("R$ ", ""),
            f"{c.get('fator_total', 1):.3f}",
            formatar_brl(c.get("valor_homogeneizado")).replace("R$ ", ""),
        ]
        aligns = ["L", "R", "R", "R", "R", "R"]
        for w, t, a in zip(larguras, vals, aligns):
            pdf.cell(w, 6, _s(t), border=1, align=a)
        pdf.ln()
        pdf.set_text_color(*ID.RGB_TEXTO)


def gerar_apresentacao(dados: dict, fotos: list[dict] | None = None,
                       avaliador: dict | None = None) -> bytes:
    """Versão resumida e visual para entregar ao cliente."""
    av = avaliador or {}
    pdf = _BasePDF()
    pdf.avaliador = av
    pdf.titulo_doc = "Apresentação da Avaliação"
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    resultado = dados.get("resultado", {})
    imovel = dados.get("imovel", {})
    tipo = dados.get("tipo_rotulo", dados.get("tipo_imovel", ""))

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*ID.RGB_PRIMARIA)
    pdf.cell(0, 8, _s("Avaliação do seu imóvel"), ln=1, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    pdf.cell(0, 6, _s(f"{tipo} - {imovel.get('bairro', '')}, {imovel.get('cidade_uf', '')}"),
             ln=1, align="C")
    pdf.ln(6)

    pdf.set_fill_color(*ID.RGB_SUCESSO)
    pdf.set_text_color(255, 255, 255)
    y = pdf.get_y()
    pdf.rect(pdf.l_margin, y, pdf.w - pdf.l_margin - pdf.r_margin, 26, "F")
    pdf.set_xy(pdf.l_margin, y + 4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, _s("Valor de mercado estimado"), ln=1, align="C")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, _s(formatar_brl(resultado.get("valor_total"))), ln=1, align="C")
    pdf.ln(8)
    pdf.set_text_color(*ID.RGB_TEXTO)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _s(f"Faixa de negociação: {formatar_brl(resultado.get('valor_min_arbitrio'))} "
                      f"a {formatar_brl(resultado.get('valor_max_arbitrio'))}"), ln=1, align="C")
    pdf.ln(4)

    pdf.titulo_secao("O imóvel")
    pdf.linha_dado("Endereço:", imovel.get("endereco"))
    pdf.linha_dado("Bairro:", imovel.get("bairro"))
    pdf.linha_dado("Cidade/UF:", imovel.get("cidade_uf"))
    if fotos:
        pdf.ln(1)
        _galeria_fotos(pdf, fotos, altura_max=70)

    pdf.titulo_secao("Como chegamos a este valor")
    pdf.par("A avaliação utilizou o Método Comparativo Direto de Dados de Mercado: "
            "comparamos seu imóvel com imóveis semelhantes, ajustando as diferenças "
            f"(localização, área, conservação e padrão). Foram usados "
            f"{resultado.get('n_comparaveis_usados', 0)} imóveis de referência.")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _s(av.get("nome", "")), ln=1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ID.RGB_TEXTO_SUAVE)
    titulo = av.get("titulo", "")
    creci = av.get("creci", "")
    if titulo or creci:
        pdf.cell(0, 5, _s(f"{titulo} - {creci}" if creci else titulo), ln=1)
    contato = " · ".join(_so_preenchidos(av.get("telefone"), av.get("email_contato")))
    if contato:
        pdf.cell(0, 5, _s(contato), ln=1)

    return bytes(pdf.output())
