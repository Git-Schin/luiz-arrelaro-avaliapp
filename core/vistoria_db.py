"""CRUD das vistorias no Supabase (tabela `vistorias`)."""
from __future__ import annotations

from datetime import datetime, timezone

from core.supa import TABELA_VISTORIAS, client

STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
TIPO_ENTRADA = "entrada"
TIPO_SAIDA = "saida"


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _payload(dados: dict, status: str) -> dict:
    ident = dados.get("identificacao") or {}
    return {
        "tipo":                 dados.get("tipo") or TIPO_ENTRADA,
        "vistoria_entrada_id":  dados.get("vistoria_entrada_id") or None,
        "status":               status,
        "endereco":             ident.get("endereco") or None,
        "cidade_uf":            ident.get("cidade_uf") or None,
        "locatario_nome":       ident.get("locatario_nome") or None,
        "data_vistoria":        ident.get("data_vistoria") or None,
        "dados":                dados,
        "atualizado_em":        _agora_iso(),
    }


def salvar(dados: dict, user_id: str | None = None,
           vistoria_id: int | None = None,
           status: str = STATUS_CONCLUIDO) -> int:
    """Cria (id None) ou atualiza (id informado). Retorna o id."""
    row = _payload(dados, status)
    if user_id:
        row["user_id"] = user_id
    tab = client().table(TABELA_VISTORIAS)
    if vistoria_id is None:
        row["criado_em"] = row["atualizado_em"]
        resp = tab.insert(row).execute()
        if not resp.data:
            raise RuntimeError("Insert retornou vazio.")
        return int(resp.data[0]["id"])
    tab.update(row).eq("id", vistoria_id).execute()
    return int(vistoria_id)


def salvar_rascunho(dados: dict, user_id: str | None = None,
                    vistoria_id: int | None = None) -> int:
    return salvar(dados, user_id=user_id, vistoria_id=vistoria_id,
                  status=STATUS_RASCUNHO)


def listar(user_id: str | None = None, busca: str = "",
           status: str | None = None, tipo: str | None = None) -> list[dict]:
    q = client().table(TABELA_VISTORIAS).select("*")
    if user_id:
        q = q.eq("user_id", user_id)
    if busca:
        pat = f"*{busca}*"
        q = q.or_(
            f"endereco.ilike.{pat},locatario_nome.ilike.{pat},cidade_uf.ilike.{pat}"
        )
    if status:
        q = q.eq("status", status)
    if tipo:
        q = q.eq("tipo", tipo)
    return list(q.order("atualizado_em", desc=True).execute().data or [])


def obter(vistoria_id: int, user_id: str | None = None) -> dict | None:
    q = (client().table(TABELA_VISTORIAS)
         .select("*").eq("id", vistoria_id))
    if user_id:
        q = q.eq("user_id", user_id)
    resp = q.limit(1).execute()
    if not resp.data:
        return None
    row = dict(resp.data[0])
    row.setdefault("dados", {})
    return row


def excluir(vistoria_id: int, user_id: str | None = None) -> None:
    q = client().table(TABELA_VISTORIAS).delete().eq("id", vistoria_id)
    if user_id:
        q = q.eq("user_id", user_id)
    q.execute()


def listar_entradas_concluidas(user_id: str | None = None) -> list[dict]:
    """Para vincular vistoria de saída com uma entrada existente."""
    q = (client().table(TABELA_VISTORIAS)
         .select("id,endereco,cidade_uf,locatario_nome,data_vistoria")
         .eq("tipo", TIPO_ENTRADA)
         .eq("status", STATUS_CONCLUIDO))
    if user_id:
        q = q.eq("user_id", user_id)
    return list(q.order("atualizado_em", desc=True).execute().data or [])
