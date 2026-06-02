-- Avaliapp · schema Postgres (Supabase)
-- Idempotente: pode rodar várias vezes sem efeito colateral.

create table if not exists avaliacoes (
    id              bigserial primary key,
    criado_em       timestamptz not null default now(),
    atualizado_em   timestamptz not null default now(),
    tipo_imovel     text,
    solicitante     text,
    endereco        text,
    cidade_uf       text,
    valor_total     numeric(14, 2),
    grau            text,
    status          text not null default 'concluido',
    passo_atual     integer not null default 1,
    dados           jsonb not null default '{}'::jsonb
);

create index if not exists idx_avaliacoes_atualizado_em
    on avaliacoes (atualizado_em desc);
create index if not exists idx_avaliacoes_status
    on avaliacoes (status);

-- Tabela é acessada via service_role; RLS opcional para defesa em profundidade.
-- Mantemos RLS desligada por ora (login do app é único, sem multitenancy).
alter table avaliacoes disable row level security;
