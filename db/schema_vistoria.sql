-- AvaliApp · Módulo de Vistoria de Imóvel para Locação
-- Rodar no SQL Editor do Supabase.
-- Idempotente: pode rodar várias vezes sem efeito colateral.

-- Tabela principal de vistorias
create table if not exists vistorias (
    id                   bigserial primary key,
    user_id              uuid references auth.users(id) on delete set null,
    tipo                 varchar(10) not null default 'entrada'
                             check (tipo in ('entrada', 'saida')),
    vistoria_entrada_id  bigint references vistorias(id) on delete set null,
    status               varchar(20) not null default 'rascunho',
    -- Campos indexados para listagem rápida
    endereco             text,
    cidade_uf            text,
    locatario_nome       text,
    data_vistoria        date,
    -- JSON completo (cômodos, itens, fotos-meta, fechamento)
    dados                jsonb not null default '{}',
    criado_em            timestamptz not null default now(),
    atualizado_em        timestamptz not null default now()
);

-- Índices para queries de listagem
create index if not exists idx_vistorias_user_id
    on vistorias (user_id);

create index if not exists idx_vistorias_tipo
    on vistorias (tipo);

-- RLS desligada: dados filtrados por user_id no código da aplicação
-- (padrão do projeto, consistente com a tabela avaliacoes)
alter table vistorias disable row level security;

-- Bucket de Storage para fotos das vistorias
-- Criar manualmente no painel do Supabase: Storage → New bucket
-- Nome: avaliapp-vistorias  |  Visibilidade: Private
