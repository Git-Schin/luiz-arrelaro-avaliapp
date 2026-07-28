"""
Persistência das avaliações e perfis de usuário em Postgres via Supabase.

Interface pública:
  Avaliações: salvar, salvar_rascunho, marcar_concluido, listar, obter, excluir
  Perfis:     obter_perfil, salvar_perfil
  Constantes: STATUS_RASCUNHO, STATUS_CONCLUIDO

Todas as operações de avaliação recebem `user_id` para isolar dados por usuário.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.supa import TABELA_AVALIACOES, TABELA_PERFIS, client

STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"


def init_db() -> None:
    """Testa a conexão ao iniciar (falha cedo se credenciais erradas)."""
    client().table(TABELA_AVALIACOES).select("id").limit(1).execute()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _payload(dados: dict, status: str, passo_atual: int) -> dict:
    imovel = dados.get("imovel", {}) or {}
    resultado = dados.get("resultado", {}) or {}
    return {
        "tipo_imovel": dados.get("tipo_imovel") or None,
        "solicitante": imovel.get("solicitante") or None,
        "endereco": imovel.get("endereco") or None,
        "cidade_uf": imovel.get("cidade_uf") or None,
        "valor_total": float(resultado.get("valor_total") or 0.0) or None,
        "grau": resultado.get("grau_fundamentacao") or None,
        "status": status,
        "passo_atual": int(passo_atual or 1),
        "dados": dados,
        "atualizado_em": _agora_iso(),
    }


def salvar(dados: dict, user_id: str | None = None,
           avaliacao_id: int | None = None,
           status: str = STATUS_CONCLUIDO, passo_atual: int = 1) -> int:
    """Cria (id None) ou atualiza (id informado) uma avaliação. Retorna o id."""
    row = _payload(dados, status, passo_atual)
    if user_id:
        row["user_id"] = user_id
    tabela = client().table(TABELA_AVALIACOES)
    if avaliacao_id is None:
        row["criado_em"] = row["atualizado_em"]
        resp = tabela.insert(row).execute()
        if not resp.data:
            raise RuntimeError("Insert retornou vazio.")
        return int(resp.data[0]["id"])
    tabela.update(row).eq("id", avaliacao_id).execute()
    return int(avaliacao_id)


def salvar_rascunho(dados: dict, user_id: str | None = None,
                    avaliacao_id: int | None = None, passo_atual: int = 1) -> int:
    return salvar(dados, user_id=user_id, avaliacao_id=avaliacao_id,
                  status=STATUS_RASCUNHO, passo_atual=passo_atual)


def marcar_concluido(avaliacao_id: int, passo_atual: int = 5) -> None:
    client().table(TABELA_AVALIACOES).update({
        "status": STATUS_CONCLUIDO,
        "passo_atual": int(passo_atual),
        "atualizado_em": _agora_iso(),
    }).eq("id", avaliacao_id).execute()


def listar(user_id: str | None = None, busca: str = "",
           status: str | None = None) -> list[dict]:
    """Lista avaliações do usuário, ordenadas por atualizado_em desc."""
    q = client().table(TABELA_AVALIACOES).select("*")
    if user_id:
        q = q.eq("user_id", user_id)
    if busca:
        pat = f"*{busca}*"
        q = q.or_(
            f"solicitante.ilike.{pat},endereco.ilike.{pat},cidade_uf.ilike.{pat}"
        )
    if status:
        q = q.eq("status", status)
    resp = q.order("atualizado_em", desc=True).execute()
    return list(resp.data or [])


def obter(avaliacao_id: int, user_id: str | None = None) -> dict | None:
    """Devolve a linha da avaliação. Se user_id informado, valida propriedade."""
    q = client().table(TABELA_AVALIACOES).select("*").eq("id", avaliacao_id)
    if user_id:
        q = q.eq("user_id", user_id)
    resp = q.limit(1).execute()
    if not resp.data:
        return None
    row = dict(resp.data[0])
    row.setdefault("dados", {})
    return row


def excluir(avaliacao_id: int, user_id: str | None = None) -> None:
    q = client().table(TABELA_AVALIACOES).delete().eq("id", avaliacao_id)
    if user_id:
        q = q.eq("user_id", user_id)
    q.execute()


# ---------------------------------------------------------------------------
# Perfis de usuário
# ---------------------------------------------------------------------------

def obter_perfil(user_id: str) -> dict | None:
    resp = (
        client().table(TABELA_PERFIS)
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return dict(resp.data[0]) if resp.data else None


def salvar_perfil(user_id: str, perfil: dict) -> None:
    """Upsert do perfil. `perfil` pode conter qualquer subconjunto dos campos."""
    row = {k: v for k, v in perfil.items()
           if k in ("nome", "titulo", "creci", "cnai",
                    "telefone", "whatsapp", "email_contato", "cidade_uf")}
    row["id"] = user_id
    row["atualizado_em"] = _agora_iso()
    client().table(TABELA_PERFIS).upsert(row).execute()
