"""
Modelo de campos do imóvel avaliando, por tipo.

Estrutura data-driven: cada tipo de imóvel define grupos de campos, e a tela de
Nova Avaliação renderiza o formulário automaticamente a partir daqui. Para mudar
um campo, edita-se só este arquivo.

Cada campo é um dict:
  key          identificador único (sem espaços)
  label        rótulo exibido
  tipo         "text" | "number" | "select" | "date" | "textarea" | "checkbox"
  opcoes       lista (apenas para select)
  obrigatorio  bool
  unidade      sufixo exibido (ex: "m²", "anos")
  ajuda        tooltip
  default      valor inicial (opcional)

⚠️ Campos baseados na NBR 14653-2 e no Manual de Avaliação de Imóveis da União 2024.
Revisar/ajustar conforme a prática do Luiz.
"""

# Opções reutilizadas
PADRAO_CONSTRUTIVO = [
    "Mínimo", "Baixo", "Normal/Médio", "Alto", "Luxo",
]
ESTADO_CONSERVACAO = [
    "Novo",
    "Entre novo e regular (pequenos reparos)",
    "Regular",
    "Entre regular e reparos simples",
    "Reparos simples",
    "Entre reparos simples e importantes",
    "Reparos importantes",
    "Entre reparos importantes e sem valor",
]
# Fonte do comparável (origem do dado de mercado). Lista das mais usadas na
# prática + "Outra" para casos não cobertos.
FONTE_COMPARAVEL = [
    "Anúncio — OLX",
    "Anúncio — ZAP Imóveis",
    "Anúncio — Viva Real",
    "Anúncio — Imovelweb",
    "Anúncio — QuintoAndar",
    "Anúncio — Chaves na Mão",
    "Anúncio — outro portal",
    "Imobiliária",
    "Corretor parceiro",
    "Proprietário",
    "Transação efetivada",
    "Cartório / Registro de Imóveis",
    "Pesquisa de campo",
    "Outra",
]
def normalizar_fonte(texto: str) -> str:
    """Mapeia texto livre (de IA/CSV) para uma opção de FONTE_COMPARAVEL."""
    t = (texto or "").lower()
    portais = {
        "olx": "Anúncio — OLX", "zap": "Anúncio — ZAP Imóveis",
        "viva": "Anúncio — Viva Real", "imovelweb": "Anúncio — Imovelweb",
        "quinto": "Anúncio — QuintoAndar", "chaves": "Anúncio — Chaves na Mão",
    }
    for chave, rotulo in portais.items():
        if chave in t:
            return rotulo
    if "imobili" in t:
        return "Imobiliária"
    if "corretor" in t:
        return "Corretor parceiro"
    if "propriet" in t:
        return "Proprietário"
    if "cart" in t or "registro" in t:
        return "Cartório / Registro de Imóveis"
    if any(p in t for p in ("portal", "anuncio", "anúncio", "site")):
        return "Anúncio — outro portal"
    if not t.strip():
        return ""
    return "Outra"


POSICAO_SOLAR = ["Indiferente", "Manhã (leste)", "Tarde (oeste)", "Norte", "Sul"]
TOPOGRAFIA = ["Plano", "Aclive", "Declive", "Irregular"]
SITUACAO_TERRENO = ["Meio de quadra", "Esquina", "Encravado", "Frente para duas ruas"]

# --- Grupos comuns a todos os tipos ---
GRUPO_IDENTIFICACAO = {
    "titulo": "Identificação",
    "campos": [
        {"key": "finalidade", "label": "Finalidade da avaliação", "tipo": "select",
         "opcoes": ["Venda/compra", "Locação", "Garantia", "Partilha/inventário",
                    "Judicial (subsídio)", "Dação em pagamento", "Outra"],
         "obrigatorio": True, "ajuda": "Para que serve esta avaliação."},
        {"key": "solicitante", "label": "Solicitante / Cliente", "tipo": "text",
         "obrigatorio": True, "ajuda": "Nome de quem pediu a avaliação."},
        {"key": "matricula", "label": "Matrícula (Registro de Imóveis)", "tipo": "text"},
        {"key": "inscricao_iptu", "label": "Inscrição IPTU", "tipo": "text"},
    ],
}
GRUPO_LOCALIZACAO = {
    "titulo": "Localização",
    "campos": [
        {"key": "cep", "label": "CEP", "tipo": "text",
         "ajuda": "Digite o CEP e clique em 'Buscar' para preencher logradouro, bairro e cidade."},
        {"key": "endereco", "label": "Logradouro / Rua", "tipo": "text", "obrigatorio": True,
         "ajuda": "Preenchido pelo CEP — confira."},
        {"key": "numero", "label": "Número", "tipo": "text",
         "ajuda": "CEP não traz o número — digite aqui."},
        {"key": "nome_condominio", "label": "Condomínio / Edifício", "tipo": "text",
         "ajuda": "Nome do condomínio ou edifício, se houver. Essencial para a IA buscar comparáveis no mesmo empreendimento."},
        {"key": "bairro", "label": "Bairro", "tipo": "text", "obrigatorio": True,
         "ajuda": "Preenchido pelo CEP — confira."},
        {"key": "cidade_uf", "label": "Cidade/UF", "tipo": "text", "obrigatorio": True,
         "ajuda": "Preenchido pelo CEP — confira."},
        {"key": "geo", "label": "Geolocalização (lat, long)", "tipo": "text",
         "ajuda": "Preenchido automaticamente quando todo o endereço estiver completo. "
                   "Pode editar manualmente — ex: -23.5505, -46.6333."},
        {"key": "infraestrutura", "label": "Infraestrutura do entorno", "tipo": "textarea",
         "ajuda": "Água, esgoto, energia, pavimentação, transporte, comércio, escolas..."},
    ],
}

# Campo de conservação (entra em quase todos os que têm construção)
CAMPO_CONSERVACAO = {
    "key": "conservacao", "label": "Estado de conservação", "tipo": "select",
    "opcoes": ESTADO_CONSERVACAO, "obrigatorio": True,
    "ajuda": "Critério Ross-Heidecke (entra no fator conservação).",
}
CAMPO_PADRAO = {
    "key": "padrao", "label": "Padrão construtivo/acabamento", "tipo": "select",
    "opcoes": PADRAO_CONSTRUTIVO, "obrigatorio": True,
}
CAMPO_IDADE = {
    "key": "idade", "label": "Idade aparente", "tipo": "number", "unidade": "anos",
    "ajuda": "Idade efetiva considerando reformas.",
}


TIPOS_IMOVEL = {
    "apartamento": {
        "rotulo": "Apartamento",
        "icone": "🏢",
        "area_base_key": "area_privativa",  # área usada como base do R$/m²
        "grupos": [
            GRUPO_IDENTIFICACAO,
            GRUPO_LOCALIZACAO,
            {"titulo": "Características do imóvel", "campos": [
                {"key": "area_privativa", "label": "Área privativa", "tipo": "number",
                 "unidade": "m²", "obrigatorio": True},
                {"key": "area_total", "label": "Área total (com comum)", "tipo": "number", "unidade": "m²"},
                {"key": "andar", "label": "Andar/Pavimento", "tipo": "number"},
                {"key": "quartos", "label": "Quartos", "tipo": "number"},
                {"key": "suites", "label": "Suítes", "tipo": "number"},
                {"key": "banheiros", "label": "Banheiros", "tipo": "number"},
                {"key": "vagas", "label": "Vagas de garagem", "tipo": "number"},
                {"key": "varanda", "label": "Varanda/Sacada", "tipo": "checkbox"},
                CAMPO_IDADE, CAMPO_PADRAO, CAMPO_CONSERVACAO,
                {"key": "posicao_solar", "label": "Posição solar", "tipo": "select", "opcoes": POSICAO_SOLAR},
                {"key": "elevadores", "label": "Elevadores no prédio", "tipo": "number"},
                {"key": "condominio", "label": "Valor do condomínio", "tipo": "number", "unidade": "R$/mês"},
                {"key": "lazer", "label": "Itens de lazer do condomínio", "tipo": "textarea"},
            ]},
        ],
    },
    "casa": {
        "rotulo": "Casa",
        "icone": "🏠",
        "area_base_key": "area_construida",
        "grupos": [
            GRUPO_IDENTIFICACAO,
            GRUPO_LOCALIZACAO,
            {"titulo": "Características do imóvel", "campos": [
                {"key": "area_terreno", "label": "Área do terreno", "tipo": "number",
                 "unidade": "m²", "obrigatorio": True},
                {"key": "area_construida", "label": "Área construída", "tipo": "number",
                 "unidade": "m²", "obrigatorio": True},
                {"key": "pavimentos", "label": "Pavimentos", "tipo": "number"},
                {"key": "quartos", "label": "Quartos", "tipo": "number"},
                {"key": "suites", "label": "Suítes", "tipo": "number"},
                {"key": "banheiros", "label": "Banheiros", "tipo": "number"},
                {"key": "vagas", "label": "Vagas de garagem", "tipo": "number"},
                CAMPO_IDADE, CAMPO_PADRAO, CAMPO_CONSERVACAO,
                {"key": "topografia", "label": "Topografia do terreno", "tipo": "select", "opcoes": TOPOGRAFIA},
                {"key": "benfeitorias", "label": "Benfeitorias (piscina, edícula, etc.)", "tipo": "textarea"},
            ]},
        ],
    },
    "terreno": {
        "rotulo": "Terreno / Lote",
        "icone": "🟫",
        "area_base_key": "area_terreno",
        "grupos": [
            GRUPO_IDENTIFICACAO,
            GRUPO_LOCALIZACAO,
            {"titulo": "Características do terreno", "campos": [
                {"key": "area_terreno", "label": "Área do terreno", "tipo": "number",
                 "unidade": "m²", "obrigatorio": True},
                {"key": "testada", "label": "Testada (frente)", "tipo": "number", "unidade": "m"},
                {"key": "profundidade", "label": "Profundidade", "tipo": "number", "unidade": "m"},
                {"key": "topografia", "label": "Topografia", "tipo": "select", "opcoes": TOPOGRAFIA},
                {"key": "situacao", "label": "Situação na quadra", "tipo": "select", "opcoes": SITUACAO_TERRENO},
                {"key": "zoneamento", "label": "Zoneamento / uso permitido", "tipo": "text"},
                {"key": "coef_aproveitamento", "label": "Coef. de aproveitamento", "tipo": "number"},
                {"key": "taxa_ocupacao", "label": "Taxa de ocupação", "tipo": "number", "unidade": "%"},
                {"key": "muro_calcada", "label": "Possui muro/calçada", "tipo": "checkbox"},
            ]},
        ],
    },
    "comercial": {
        "rotulo": "Comercial (sala/loja/galpão)",
        "icone": "🏬",
        "area_base_key": "area_util",
        "grupos": [
            GRUPO_IDENTIFICACAO,
            GRUPO_LOCALIZACAO,
            {"titulo": "Características do imóvel", "campos": [
                {"key": "subtipo", "label": "Tipo", "tipo": "select",
                 "opcoes": ["Sala/conjunto", "Loja", "Galpão", "Prédio comercial", "Outro"]},
                {"key": "area_util", "label": "Área útil/privativa", "tipo": "number",
                 "unidade": "m²", "obrigatorio": True},
                {"key": "pe_direito", "label": "Pé-direito", "tipo": "number", "unidade": "m"},
                {"key": "testada", "label": "Testada/visibilidade", "tipo": "number", "unidade": "m"},
                {"key": "vagas", "label": "Vagas", "tipo": "number"},
                CAMPO_IDADE, CAMPO_PADRAO, CAMPO_CONSERVACAO,
                {"key": "fluxo", "label": "Fluxo/localização comercial", "tipo": "textarea",
                 "ajuda": "Avenida movimentada, centro, galeria, etc."},
                {"key": "aluguel_referencia", "label": "Aluguel de referência (se houver)",
                 "tipo": "number", "unidade": "R$/mês"},
            ]},
        ],
    },
    "rural": {
        "rotulo": "Rural",
        "icone": "🌾",
        "area_base_key": "area_total_ha",
        "grupos": [
            GRUPO_IDENTIFICACAO,
            GRUPO_LOCALIZACAO,
            {"titulo": "Características do imóvel rural", "campos": [
                {"key": "area_total_ha", "label": "Área total", "tipo": "number",
                 "unidade": "ha", "obrigatorio": True},
                {"key": "capacidade_uso", "label": "Capacidade de uso do solo", "tipo": "textarea"},
                {"key": "recursos_hidricos", "label": "Recursos hídricos", "tipo": "textarea"},
                {"key": "culturas", "label": "Culturas / pastagens", "tipo": "textarea"},
                {"key": "benfeitorias", "label": "Benfeitorias (reprodutivas e não)", "tipo": "textarea"},
                {"key": "acesso", "label": "Acesso (estrada/distância)", "tipo": "text"},
                {"key": "georreferenciamento", "label": "CAR / CCIR / georreferenciamento", "tipo": "text"},
            ]},
        ],
    },
}


def listar_tipos():
    """Retorna [(key, 'Ícone Rótulo'), ...] para selectbox."""
    return [(k, f"{v['icone']} {v['rotulo']}") for k, v in TIPOS_IMOVEL.items()]


def get_tipo(key: str) -> dict:
    return TIPOS_IMOVEL[key]
