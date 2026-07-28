-- AvaliApp · migração v2: multi-usuário
-- Rodar no SQL Editor do Supabase DEPOIS do schema.sql original.
-- Idempotente: pode rodar várias vezes sem efeito colateral.

-- 1. Adiciona user_id à tabela de avaliações
alter table avaliacoes
    add column if not exists user_id uuid references auth.users(id) on delete set null;

create index if not exists idx_avaliacoes_user_id
    on avaliacoes (user_id);

-- 2. Tabela de perfis (1 por usuário autenticado)
create table if not exists perfis (
    id              uuid primary key references auth.users(id) on delete cascade,
    nome            text,
    titulo          text not null default 'Corretor de Imóveis',
    creci           text,
    cnai            text,
    telefone        text,
    whatsapp        text,
    email_contato   text,
    cidade_uf       text,
    atualizado_em   timestamptz not null default now()
);

-- RLS desligada por ora (dados filtrados por user_id no código da aplicação).
alter table perfis disable row level security;

-- Vincula avaliações existentes (banco em branco, mas por segurança deixamos NULL).
-- Se quiser atribuir todas ao primeiro usuário: UPDATE avaliacoes SET user_id = '<uuid>';
