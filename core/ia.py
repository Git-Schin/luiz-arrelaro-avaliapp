"""
Camada de IA do Avaliapp — PLUGÁVEL (provedor trocável sem mexer no app).

Provedor padrão: **Google Gemini** (tem free tier real, cobre redação + análise +
OCR de imagem/PDF). A interface `ProvedorIA` deixa pronto trocar para Claude,
Ollama (local) ou outro, mudando só a configuração.

Funções de alto nível usadas pelas telas:
  - status()                      -> diz se a IA está configurada (e qual provedor)
  - redigir_secao(secao, dados)   -> texto pronto para uma seção do PTAM
  - analisar_comparaveis(dados)   -> análise crítica / outliers da pesquisa
  - ocr_documento(conteudo, mime) -> extrai campos de matrícula/IPTU (imagem ou PDF)

⚠️ "Humano no circuito": tudo o que a IA gera é SUGESTÃO. O Luiz revisa, edita e
assina. Sem chave/provedor configurado, as funções retornam um aviso amigável
(`RespostaIA.ok = False`) em vez de quebrar o app — o fluxo manual segue intacto.

Configuração da chave (qualquer um dos caminhos):
  1) .streamlit/secrets.toml:
        [ia]
        provedor = "gemini"
        api_key  = "SUA_CHAVE"
        modelo   = "gemini-2.0-flash"   # opcional
  2) variável de ambiente: GEMINI_API_KEY  (e, opcional, AVALIAPP_IA_MODELO)

A chave do Gemini é gratuita em https://aistudio.google.com/app/apikey
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field

# requests acompanha o Streamlit; importado preguiçosamente para não obrigar
# dependência em quem só usa o núcleo de cálculo.
GEMINI_MODELO_PADRAO = "gemini-2.5-flash"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
_TIMEOUT = 60


@dataclass
class RespostaIA:
    """Resultado de qualquer chamada de IA. `ok=False` => mostrar `erro` ao usuário."""
    ok: bool
    texto: str = ""
    erro: str = ""
    campos: dict = field(default_factory=dict)        # usado pelo OCR (campos extraídos)
    comparaveis: list = field(default_factory=list)   # usado pela busca de comparáveis


# ---------------------------------------------------------------------------
# Configuração (secrets do Streamlit OU variáveis de ambiente)
# ---------------------------------------------------------------------------
def _config() -> dict:
    """Resolve provedor/chave/modelo. Não falha fora de um contexto Streamlit."""
    cfg = {"provedor": "gemini", "api_key": "", "modelo": ""}
    try:
        import streamlit as st
        sec = dict(st.secrets.get("ia", {})) if hasattr(st, "secrets") else {}
        cfg.update({k: sec[k] for k in ("provedor", "api_key", "modelo") if k in sec})
    except Exception:
        pass
    # Ambiente sobrepõe se preenchido
    cfg["api_key"] = cfg["api_key"] or os.environ.get("GEMINI_API_KEY", "")
    cfg["modelo"] = cfg["modelo"] or os.environ.get("AVALIAPP_IA_MODELO", "")
    cfg["provedor"] = os.environ.get("AVALIAPP_IA_PROVEDOR", "") or cfg["provedor"] or "gemini"
    return cfg


# ---------------------------------------------------------------------------
# Interface de provedor (contrato extensível)
# ---------------------------------------------------------------------------
class ProvedorIA:
    nome = "base"

    def disponivel(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def gerar(self, prompt: str, sistema: str = "", temperatura: float = 0.4) -> RespostaIA:  # pragma: no cover
        raise NotImplementedError

    def ocr(self, conteudo: bytes, mime: str, instrucao: str) -> RespostaIA:  # pragma: no cover
        raise NotImplementedError


class GeminiProvedor(ProvedorIA):
    nome = "gemini"

    def __init__(self, api_key: str, modelo: str = ""):
        self.api_key = api_key
        self.modelo = modelo or GEMINI_MODELO_PADRAO

    def disponivel(self) -> bool:
        return bool(self.api_key)

    # -- chamada HTTP única ao endpoint generateContent --
    def _chamar(self, partes: list[dict], sistema: str = "",
                temperatura: float = 0.4, ferramentas: list[dict] | None = None,
                sem_pensamento: bool = False) -> RespostaIA:
        if not self.api_key:
            return RespostaIA(False, erro="IA não configurada (sem chave do Gemini).")
        try:
            import requests
        except ImportError:
            return RespostaIA(False, erro="Biblioteca 'requests' indisponível para chamar a IA.")

        corpo: dict = {
            "contents": [{"role": "user", "parts": partes}],
            # 8192 = teto de saída do gemini-*-flash. 2048 truncava análises/seções longas.
            "generationConfig": {"temperature": temperatura, "maxOutputTokens": 8192},
        }
        if sistema:
            corpo["system_instruction"] = {"parts": [{"text": sistema}]}
        if ferramentas:
            corpo["tools"] = ferramentas
        if sem_pensamento:
            # gemini-2.5 gasta "thinking tokens" do orçamento; desligar deixa
            # mais espaço para a saída (evita MAX_TOKENS) e acelera tarefas objetivas.
            corpo["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

        url = GEMINI_ENDPOINT.format(modelo=self.modelo)
        # 503/500 = sobrecarga temporária do modelo: 1 retentativa com backoff curto.
        r = None
        for tentativa in range(2):
            try:
                r = requests.post(url, headers={"x-goog-api-key": self.api_key},
                                  json=corpo, timeout=_TIMEOUT)
            except Exception as e:  # rede/timeout
                return RespostaIA(False, erro=f"Falha de conexão com a IA: {e}")
            if r.status_code not in (500, 503) or tentativa == 1:
                break
            import time
            time.sleep(3)

        if r.status_code != 200:
            detalhe = ""
            try:
                detalhe = r.json().get("error", {}).get("message", "")
            except Exception:
                detalhe = r.text[:200]
            if r.status_code in (401, 403):
                detalhe = "chave inválida ou sem permissão. " + detalhe
            elif r.status_code == 429:
                detalhe = "limite do free tier atingido — tente mais tarde. " + detalhe
            return RespostaIA(False, erro=f"IA retornou {r.status_code}: {detalhe}")

        try:
            dados = r.json()
            cands = dados.get("candidates") or []
            if not cands:
                return RespostaIA(False, erro="A IA não retornou nenhuma resposta.")
            cand = cands[0]
            motivo = cand.get("finishReason", "")
            if motivo == "SAFETY":
                return RespostaIA(False, erro="A IA bloqueou a resposta por filtro de segurança.")
            partes_resp = cand.get("content", {}).get("parts")
            if not partes_resp:
                # sem 'parts': normalmente orçamento esgotado antes de emitir o texto
                if motivo == "MAX_TOKENS":
                    return RespostaIA(False, erro=(
                        "A IA atingiu o limite de tokens antes de concluir a resposta. "
                        "Tente novamente."))
                return RespostaIA(False, erro=(
                    f"A IA não retornou conteúdo (motivo: {motivo or 'desconhecido'})."))
            texto = "".join(p.get("text", "") for p in partes_resp).strip()
            if not texto:
                return RespostaIA(False, erro="A IA retornou resposta vazia.")
            return RespostaIA(True, texto=texto)
        except (KeyError, IndexError, ValueError) as e:
            return RespostaIA(False, erro=f"Resposta da IA em formato inesperado: {e}")

    def gerar(self, prompt: str, sistema: str = "", temperatura: float = 0.4) -> RespostaIA:
        return self._chamar([{"text": prompt}], sistema=sistema, temperatura=temperatura)

    def buscar(self, prompt: str, sistema: str = "", temperatura: float = 0.3) -> RespostaIA:
        """Gera com pesquisa Google (grounding) ativada — para comparáveis na web."""
        return self._chamar([{"text": prompt}], sistema=sistema, temperatura=temperatura,
                            ferramentas=[{"google_search": {}}], sem_pensamento=True)

    def ocr(self, conteudo: bytes, mime: str, instrucao: str) -> RespostaIA:
        b64 = base64.b64encode(conteudo).decode("ascii")
        partes = [{"text": instrucao}, {"inline_data": {"mime_type": mime, "data": b64}}]
        return self._chamar(partes, temperatura=0.1)


def _provedor() -> ProvedorIA | None:
    cfg = _config()
    if cfg["provedor"] == "gemini":
        return GeminiProvedor(cfg["api_key"], cfg["modelo"])
    # Pontos de extensão futuros: "claude", "ollama"...
    return None


def status() -> dict:
    """Para a UI: {'configurada': bool, 'provedor': str, 'modelo': str}."""
    cfg = _config()
    prov = _provedor()
    return {
        "configurada": bool(prov and prov.disponivel()),
        "provedor": cfg["provedor"],
        "modelo": cfg["modelo"] or GEMINI_MODELO_PADRAO,
    }


# ---------------------------------------------------------------------------
# Contexto: resume a avaliação em texto compacto para os prompts
# ---------------------------------------------------------------------------
_SISTEMA_AVALIADOR = (
    "Você é assistente técnico de um Corretor de Imóveis avaliador (CRECI) no Brasil. "
    "Ajuda a redigir um Parecer Técnico de Avaliação Mercadológica (PTAM) com base na "
    "metodologia da ABNT NBR 14653 (Método Comparativo Direto). Escreva em português "
    "do Brasil, tom técnico, sóbrio e impessoal, sem inventar dados não fornecidos. "
    "Nunca prometa exatidão nem garanta valores; trate-os como estimativa de mercado. "
    "Não se refira a si mesmo nem use formatação markdown — apenas o texto da seção."
)


def _resumo_imovel(dados: dict) -> str:
    imovel = dados.get("imovel", {})
    tipo = dados.get("tipo_rotulo", dados.get("tipo_imovel", ""))
    linhas = [f"Tipo: {tipo}"]
    for grupo in dados.get("imovel_detalhado", []):
        for rotulo, valor in grupo:
            linhas.append(f"{rotulo}: {valor}")
    if not dados.get("imovel_detalhado"):  # fallback: usa o dict bruto
        for k, v in imovel.items():
            if v not in (None, "", 0, False):
                linhas.append(f"{k}: {v}")
    return "\n".join(linhas)


def _resumo_resultado(dados: dict) -> str:
    from core.calculo import formatar_brl
    r = dados.get("resultado", {})
    if not r:
        return "Avaliação ainda não calculada."
    return (
        f"Valor de mercado estimado: {formatar_brl(r.get('valor_total'))}\n"
        f"Valor unitário homogeneizado: {formatar_brl(r.get('valor_unitario_medio'))}/m²\n"
        f"Faixa (campo de arbítrio ±15%): {formatar_brl(r.get('valor_min_arbitrio'))} a "
        f"{formatar_brl(r.get('valor_max_arbitrio'))}\n"
        f"Comparáveis usados: {r.get('n_comparaveis_usados', 0)} · "
        f"Grau de fundamentação: {r.get('grau_fundamentacao', '—')} · "
        f"CV: {r.get('coef_variacao', 0):.0f}%"
    )


def _resumo_comparaveis(dados: dict) -> str:
    from core.calculo import formatar_brl
    linhas = []
    for c in dados.get("comparaveis", []):
        if not c.get("incluir"):
            continue
        marca = "" if c.get("valido", True) else " [descartado no saneamento]"
        linhas.append(
            f"- {c.get('descricao') or c.get('fonte') or 'comparável'}: "
            f"{formatar_brl(c.get('preco_total'))}, {c.get('area', 0):.0f} m², "
            f"{formatar_brl(c.get('valor_unitario'))}/m², fator {c.get('fator_total', 1):.3f}, "
            f"homog. {formatar_brl(c.get('valor_homogeneizado'))}/m²{marca}"
        )
    return "\n".join(linhas) if linhas else "Nenhum comparável incluído."


# ---------------------------------------------------------------------------
# Funções de alto nível (o que as telas chamam)
# ---------------------------------------------------------------------------
SECOES = {
    "comentario_mercado": "Comentário do mercado da região",
    "descricao_imovel": "Descrição técnica do imóvel",
    "justificativa_valor": "Justificativa da conclusão de valor",
    "pressupostos": "Pressupostos e ressalvas",
}

_INSTRUCAO_SECAO = {
    "comentario_mercado": (
        "Redija um parágrafo de comentário do mercado imobiliário pertinente ao imóvel e à "
        "sua localização, com base apenas nos dados abaixo. Se faltar informação de mercado, "
        "mantenha-se genérico e prudente, sem inventar índices ou números."
    ),
    "descricao_imovel": (
        "Redija a seção de caracterização/descrição do imóvel em prosa corrida, a partir dos "
        "dados informados, sem repetir rótulos como lista."
    ),
    "justificativa_valor": (
        "Redija a justificativa técnica da conclusão de valor, conectando o método comparativo, "
        "a homogeneização por fatores, o saneamento e o grau de fundamentação obtido."
    ),
    "pressupostos": (
        "Redija os pressupostos e ressalvas da avaliação (veracidade dos documentos, condições "
        "limitantes, data de referência, caráter mercadológico do parecer)."
    ),
}


def redigir_secao(secao: str, dados: dict) -> RespostaIA:
    """Gera o texto de uma seção do PTAM. `secao` ∈ SECOES."""
    prov = _provedor()
    if not prov or not prov.disponivel():
        return RespostaIA(False, erro="IA não configurada. Veja como ativar no aviso da página.")
    if secao not in _INSTRUCAO_SECAO:
        return RespostaIA(False, erro=f"Seção desconhecida: {secao}")

    prompt = (
        f"{_INSTRUCAO_SECAO[secao]}\n\n"
        f"=== DADOS DO IMÓVEL ===\n{_resumo_imovel(dados)}\n\n"
        f"=== PESQUISA DE MERCADO (comparáveis) ===\n{_resumo_comparaveis(dados)}\n\n"
        f"=== RESULTADO DA AVALIAÇÃO ===\n{_resumo_resultado(dados)}\n"
    )
    return prov.gerar(prompt, sistema=_SISTEMA_AVALIADOR)


def analisar_comparaveis(dados: dict) -> RespostaIA:
    """Análise crítica da pesquisa: outliers, coerência, lacunas e sugestões."""
    prov = _provedor()
    if not prov or not prov.disponivel():
        return RespostaIA(False, erro="IA não configurada. Veja como ativar no aviso da página.")
    prompt = (
        "Atue como revisor técnico da pesquisa de mercado de uma avaliação por comparação. "
        "Analise os comparáveis e o resultado abaixo e aponte, em itens curtos: (1) possíveis "
        "outliers ou preços/áreas inconsistentes; (2) dispersão (CV) e o que ela sugere; "
        "(3) lacunas (poucos dados, fatores fora de faixa); (4) sugestões objetivas de melhoria. "
        "Seja conciso e prático. Não recalcule valores.\n\n"
        f"=== IMÓVEL AVALIANDO ===\n{_resumo_imovel(dados)}\n\n"
        f"=== COMPARÁVEIS ===\n{_resumo_comparaveis(dados)}\n\n"
        f"=== RESULTADO ===\n{_resumo_resultado(dados)}\n"
    )
    return prov.gerar(prompt, sistema=_SISTEMA_AVALIADOR, temperatura=0.3)


def _num_br(v) -> float:
    """Converte número possivelmente em formato BR ('850.000,00', 'R$ 1.200') em float."""
    import re
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v or "").strip())
    if not s:
        return 0.0
    if "," in s and "." in s:        # ponto = milhar, vírgula = decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _extrair_lista_json(texto: str) -> list:
    """Recorta e carrega o primeiro array JSON encontrado no texto da IA."""
    s = (texto or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[4:].strip() if s.lower().startswith("json") else s
    i, j = s.find("["), s.rfind("]")
    if i != -1 and j != -1 and j > i:
        s = s[i:j + 1]
    try:
        data = json.loads(s)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []


_FONTES_SUGERIDAS = "OLX, ZAP Imóveis, Viva Real, Imovelweb, QuintoAndar, Chaves na Mão"


def buscar_comparaveis(imovel: dict, tipo_rotulo: str = "") -> RespostaIA:
    """
    Pesquisa anúncios reais de imóveis comparáveis na web (Gemini + Google Search).
    Retorna `comparaveis` = lista de dicts {descricao, fonte, link, preco_total,
    area, conservacao, obs} para o usuário REVISAR antes de incluir no cálculo.
    """
    prov = _provedor()
    if not prov or not prov.disponivel():
        return RespostaIA(False, erro="IA não configurada. Veja como ativar no aviso da página.")

    dados_txt = "\n".join(
        f"{k}: {v}" for k, v in imovel.items() if v not in (None, "", 0, False)
    ) or "(poucos dados informados)"

    prompt = (
        "Pesquise na web ANÚNCIOS REAIS e ATUAIS de imóveis À VENDA comparáveis ao imóvel "
        f"abaixo (tipo: {tipo_rotulo or 'imóvel'}), na MESMA cidade/bairro ou proximidades, "
        f"com porte e padrão semelhantes. Priorize os portais: {_FONTES_SUGERIDAS}.\n"
        "Traga de 5 a 8 comparáveis. Responda APENAS com um ARRAY JSON válido (sem nenhum "
        "texto fora dele e sem cercas de código). Cada item EXATAMENTE com estas chaves:\n"
        '{"descricao":"", "fonte":"", "link":"", "preco_total":0, "area":0, '
        '"conservacao":"", "obs":""}\n'
        "- preco_total: número em reais, apenas dígitos (sem 'R$' e sem separador de milhar).\n"
        "- area: número em m² (privativa/útil quando possível), com ponto decimal.\n"
        "- fonte: nome do portal/origem (ex.: OLX, ZAP, Viva Real, Imobiliária).\n"
        "- link: URL direta do anúncio.\n"
        "- conservacao e obs: opcionais (string vazia se não souber).\n"
        "NÃO invente anúncios nem links. Se não encontrar dados confiáveis, retorne [].\n\n"
        f"=== IMÓVEL AVALIANDO ===\n{dados_txt}\n"
    )
    resp = prov.buscar(prompt, sistema=_SISTEMA_AVALIADOR)
    if not resp.ok:
        return resp

    comps = []
    for it in _extrair_lista_json(resp.texto):
        if not isinstance(it, dict):
            continue
        preco, area = _num_br(it.get("preco_total")), _num_br(it.get("area"))
        if preco <= 0 and area <= 0:
            continue
        comps.append({
            "descricao": str(it.get("descricao", "")).strip(),
            "fonte": str(it.get("fonte", "")).strip(),
            "link": str(it.get("link", "")).strip(),
            "preco_total": preco,
            "area": area,
            "conservacao": str(it.get("conservacao", "")).strip(),
            "obs": str(it.get("obs", "")).strip(),
        })
    resp.comparaveis = comps
    if not comps:
        resp.erro = ("A IA não retornou comparáveis utilizáveis. Tente detalhar mais o imóvel "
                     "(bairro, cidade, área) ou faça a pesquisa manual.")
        resp.ok = False
    return resp


_OCR_INSTRUCAO = (
    "Você está lendo um documento imobiliário brasileiro (matrícula de Registro de Imóveis "
    "ou carnê/espelho de IPTU). Extraia os campos abaixo e responda APENAS com um objeto JSON "
    "válido (sem cercas de código, sem texto antes/depois), usando exatamente estas chaves "
    "(use string vazia quando não encontrar):\n"
    '{"matricula":"", "inscricao_iptu":"", "endereco":"", "bairro":"", "cidade_uf":"", '
    '"cep":"", "area_terreno":"", "area_construida":"", "area_privativa":"", '
    '"proprietario":"", "observacoes":""}\n'
    "Números de área apenas com dígitos e vírgula decimal (ex.: 78,50)."
)


def ocr_documento(conteudo: bytes, mime: str) -> RespostaIA:
    """
    Lê matrícula/IPTU (imagem JPEG/PNG ou PDF) e tenta extrair campos para
    autopreencher o formulário. Retorna `campos` (dict) + `texto` (JSON cru).
    """
    prov = _provedor()
    if not prov or not prov.disponivel():
        return RespostaIA(False, erro="IA não configurada. Veja como ativar no aviso da página.")

    resp = prov.ocr(conteudo, mime, _OCR_INSTRUCAO)
    if not resp.ok:
        return resp

    bruto = resp.texto.strip()
    # tolera cercas de código ```json ... ```
    if bruto.startswith("```"):
        bruto = bruto.strip("`")
        bruto = bruto[4:].strip() if bruto.lower().startswith("json") else bruto
    try:
        campos = json.loads(bruto)
        if isinstance(campos, dict):
            resp.campos = {k: ("" if v is None else str(v)).strip() for k, v in campos.items()}
    except (ValueError, TypeError):
        # devolve o texto cru para o usuário aproveitar manualmente
        resp.campos = {}
    return resp
