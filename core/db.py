"""
Persistência das avaliações (histórico) em Postgres via Supabase.

Mantém a mesma interface pública da versão SQLite anterior — `salvar`,
`salvar_rascunho`, `marcar_concluido`, `listar`, `obter`, `excluir`, além das
constantes `STATUS_RASCUNHO`/`STATUS_CONCLUIDO`.

Esquema (rodar `db/schema.sql` no SQL Editor do Supabase antes do primeiro uso):
- tabela `avaliacoes(id, criado_em, atualizado_em, tipo_imovel, solicitante,
  endereco, cidade_uf, valor_total, grau, status, passo_atual, dados jsonb)`

Anexos (fotos) ficam no Supabase Storage — ver `core/anexos.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.supa import TABELA_AVALIACOES, client

STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"


def init_db() -> None:
    """Compatibilidade — o schema é criado/atualizado fora do app (db/schema.sql
    rodado no Supabase). Aqui apenas testamos a conexão para falhar cedo se as
    credenciais estiverem erradas."""
    # client() já levanta SupaNaoConfigurado se faltarem credenciais.
    client().table(TABELA_AVALIACOES).select("id").limit(1).execute()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _payload(dados: dict, status: str, passo_atual: int) -> dict:
    """Monta o dict de colunas a partir do payload da avaliação."""
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


def salvar(dados: dict, avaliacao_id: int | None = None,
           status: str = STATUS_CONCLUIDO, passo_atual: int = 1) -> int:
    """Cria (id None) ou atualiza (id informado) uma avaliação. Retorna o id."""
    row = _payload(dados, status, passo_atual)
    tabela = client().table(TABELA_AVALIACOES)
    if avaliacao_id is None:
        row["criado_em"] = row["atualizado_em"]
        resp = tabela.insert(row).execute()
        if not resp.data:
            raise RuntimeError("Insert retornou vazio.")
        return int(resp.data[0]["id"])
    tabela.update(row).eq("id", avaliacao_id).execute()
    return int(avaliacao_id)


def salvar_rascunho(dados: dict, avaliacao_id: int | None, passo_atual: int) -> int:
    """Atalho para `salvar` com status='rascunho'."""
    return salvar(dados, avaliacao_id=avaliacao_id,
                  status=STATUS_RASCUNHO, passo_atual=passo_atual)


def marcar_concluido(avaliacao_id: int, passo_atual: int = 5) -> None:
    """Promove um rascunho a concluído sem rescrever o payload de dados."""
    client().table(TABELA_AVALIACOES).update({
        "status": STATUS_CONCLUIDO,
        "passo_atual": int(passo_atual),
        "atualizado_em": _agora_iso(),
    }).eq("id", avaliacao_id).execute()


def listar(busca: str = "", status: str | None = None) -> list[dict]:
    """Lista avaliações ordenadas por `atualizado_em` desc.

    `busca` casa parcialmente (case-insensitive) com solicitante/endereço/cidade.
    `status` filtra por estado quando informado.
    """
    q = client().table(TABELA_AVALIACOES).select("*")
    if busca:
        # supabase-py usa formato "col.op.value,col.op.value" para .or_()
        pat = f"*{busca}*"
        q = q.or_(
            f"solicitante.ilike.{pat},endereco.ilike.{pat},cidade_uf.ilike.{pat}"
        )
    if status:
        q = q.eq("status", status)
    resp = q.order("atualizado_em", desc=True).execute()
    return list(resp.data or [])


def obter(avaliacao_id: int) -> dict | None:
    """Devolve a linha com os campos da tabela + chave `dados` (payload)."""
    resp = (
        client().table(TABELA_AVALIACOES)
        .select("*")
        .eq("id", avaliacao_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    row = dict(resp.data[0])
    # No SQLite o payload era guardado em "dados_json" (string). No Postgres é
    # um campo JSONB chamado "dados" — já vem como dict. Mantemos a chave
    # `dados` para casar com o callers.
    row.setdefault("dados", {})
    return row


def excluir(avaliacao_id: int) -> None:
    client().table(TABELA_AVALIACOES).delete().eq("id", avaliacao_id).execute()
