"""Modelo de dados para vistoria de imóvel — cômodos, itens e estados."""
from __future__ import annotations
import uuid

# ── Estados de conservação ──────────────────────────────────────────────────
ESTADOS = ["Ótimo", "Bom", "Regular", "Ruim", "Não se aplica"]

ESTADO_COR = {
    "Ótimo":          "#059669",
    "Bom":            "#10B981",
    "Regular":        "#F59E0B",
    "Ruim":           "#DC2626",
    "Não se aplica":  "#94A3B8",
}

ESTADO_EMOJI = {
    "Ótimo":          "🟢",
    "Bom":            "🟩",
    "Regular":        "🟡",
    "Ruim":           "🔴",
    "Não se aplica":  "⚪",
}

# ── Itens padrão por tipo de cômodo ─────────────────────────────────────────
_ITENS_GERAL = [
    "Paredes/Pintura",
    "Piso",
    "Teto/Forro",
    "Portas",
    "Janelas",
    "Tomadas/Interruptores",
    "Instalação Elétrica",
    "Iluminação",
]

_ITENS_BANHEIRO = [
    "Paredes/Pintura",
    "Piso",
    "Teto/Forro",
    "Porta",
    "Box/Cortina",
    "Vaso Sanitário",
    "Pia/Cuba",
    "Torneiras/Registros",
    "Chuveiro",
    "Instalação Hidráulica",
    "Tomadas/Interruptores",
    "Iluminação",
]

_ITENS_COZINHA = [
    "Paredes/Pintura",
    "Piso",
    "Teto/Forro",
    "Portas",
    "Janelas",
    "Pia/Cuba",
    "Torneiras/Registros",
    "Instalação Hidráulica",
    "Tomadas/Interruptores",
    "Instalação Elétrica",
    "Iluminação",
]

_ITENS_AREA_SERVICO = [
    "Paredes/Pintura",
    "Piso",
    "Teto/Forro",
    "Porta",
    "Janelas",
    "Tanque",
    "Torneiras/Registros",
    "Instalação Hidráulica",
    "Tomadas/Interruptores",
    "Iluminação",
]

_ITENS_GARAGEM = [
    "Piso",
    "Paredes/Pintura",
    "Portão",
    "Iluminação",
    "Instalação Elétrica",
]

# ── Cômodos padrão (nome, ícone, itens) ─────────────────────────────────────
COMODOS_PADRAO = [
    {"nome": "Sala de Estar",   "icone": "🛋️",  "itens": _ITENS_GERAL},
    {"nome": "Sala de Jantar",  "icone": "🍽️",  "itens": _ITENS_GERAL},
    {"nome": "Cozinha",         "icone": "🍳",   "itens": _ITENS_COZINHA},
    {"nome": "Área de Serviço", "icone": "🧺",   "itens": _ITENS_AREA_SERVICO},
    {"nome": "Quarto 1",        "icone": "🛏️",  "itens": _ITENS_GERAL},
    {"nome": "Banheiro Social", "icone": "🚿",   "itens": _ITENS_BANHEIRO},
    {"nome": "Garagem",         "icone": "🚗",   "itens": _ITENS_GARAGEM},
]

ICONES_DISPONIVEIS = [
    "🏠", "🛋️", "🍽️", "🍳", "🧺", "🛏️", "🚿", "🛁", "🚗", "🌿",
    "🌳", "📦", "🏋️", "💼", "🎮", "📚", "🪟", "🚪",
]


# ── Fábricas ─────────────────────────────────────────────────────────────────

def _novo_item(nome: str) -> dict:
    return {"nome": nome, "estado": "", "obs": "", "fotos": []}


def _itens_para_nome(nome: str) -> list[str]:
    n = nome.lower()
    if any(p in n for p in ("banheiro", "lavabo", "wc", "toilet")):
        return _ITENS_BANHEIRO
    if "cozinha" in n:
        return _ITENS_COZINHA
    if any(p in n for p in ("serviço", "servico", "lavanderia")):
        return _ITENS_AREA_SERVICO
    if "garagem" in n or "estacionamento" in n:
        return _ITENS_GARAGEM
    return _ITENS_GERAL


def novo_comodo(nome: str, icone: str = "🏠") -> dict:
    return {
        "id":       str(uuid.uuid4()),
        "nome":     nome,
        "icone":    icone,
        "itens":    [_novo_item(n) for n in _itens_para_nome(nome)],
        "obs_geral": "",
        "concluido": False,
    }


def comodos_iniciais() -> list[dict]:
    return [novo_comodo(c["nome"], c["icone"]) for c in COMODOS_PADRAO]


# ── Helpers de análise ───────────────────────────────────────────────────────

def percentual_completo(comodos: list[dict]) -> float:
    if not comodos:
        return 0.0
    return sum(1 for c in comodos if c.get("concluido")) / len(comodos)


def item_entrada(comodos_entrada: list[dict], nome_comodo: str, nome_item: str) -> dict | None:
    """Busca o item correspondente na vistoria de entrada (matching por nome)."""
    nome_comodo_l = nome_comodo.lower().strip()
    nome_item_l = nome_item.lower().strip()
    for c in comodos_entrada:
        if c.get("nome", "").lower().strip() == nome_comodo_l:
            for it in c.get("itens", []):
                if it.get("nome", "").lower().strip() == nome_item_l:
                    return it
    return None


def dados_vistoria_vazio(perfil: dict | None = None) -> dict:
    """Estrutura inicial de dados de uma vistoria nova."""
    return {
        "tipo": "entrada",
        "vistoria_entrada_id": None,
        "identificacao": {
            "cep": "",
            "endereco": "",
            "numero": "",
            "bairro": "",
            "cidade_uf": "",
            "locatario_nome": "",
            "locatario_doc": "",
            "proprietario_nome": "",
            "proprietario_doc": "",
            "imobiliaria": "",
            "data_vistoria": None,
            "vistoriador_nome": (perfil or {}).get("nome", ""),
        },
        "comodos": [],
        "fechamento": {
            "chaves_quantidade": 2,
            "medidor_agua": "",
            "medidor_luz": "",
            "medidor_gas": "",
            "fotos_agua": [],
            "fotos_luz":  [],
            "fotos_gas":  [],
            "obs_gerais": "",
        },
    }
