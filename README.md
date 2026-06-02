# Avaliapp

App de **avaliação de imóveis** assistido por IA para **Luiz Arrelaro** (corretor/avaliador).
Gera **PTAM** (Parecer Técnico de Avaliação Mercadológica) pelo Método Comparativo Direto,
exporta PDF e mantém histórico das avaliações.

## Stack
- **Streamlit** (interface)
- **Supabase** — Postgres para o histórico de avaliações + Storage para as fotos
- **fpdf2** (PDF: PTAM completo + apresentação ao cliente)
- **Gemini** (Google) para apoio de IA — redação, análise de comparáveis, OCR

## Estrutura
```
Avaliapp/
├── app.py                  # entrada: login + roteador
├── config/identidade.py    # marca, cores, dados do avaliador
├── core/
│   ├── tipos_imovel.py     # campos do formulário por tipo de imóvel
│   ├── fatores.py          # fatores de homogeneização (NBR 14653)
│   ├── calculo.py          # motor de cálculo
│   ├── db.py               # persistência (Supabase/Postgres)
│   ├── anexos.py           # fotos no Supabase Storage
│   ├── supa.py             # cliente Supabase compartilhado
│   ├── pdf.py              # geração dos PDFs
│   ├── cep.py              # consulta de CEP (ViaCEP)
│   ├── geocode.py          # geocoding em cascata (Nominatim/OSM)
│   └── auth.py             # login por senha
├── pages/
│   ├── 0_Inicio.py         # central
│   ├── 1_Nova_Avaliacao.py # wizard de 5 passos
│   └── 2_Historico.py      # buscar, reabrir, baixar, excluir
├── db/schema.sql           # schema Postgres (rodar no SQL Editor do Supabase)
└── requirements.txt
```

## Primeira vez — setup do Supabase

1. Criar um projeto novo em https://supabase.com (free tier serve).
2. **SQL Editor** → cole o conteúdo de `db/schema.sql` e rode (cria a tabela `avaliacoes` e índices).
3. **Storage** → criar bucket chamado `avaliapp-anexos`, marcar como **privado**.
4. **Settings → API** → copiar:
   - `Project URL` → vai em `SUPABASE_URL`
   - `service_role` (não a anon) → vai em `SUPABASE_SERVICE_KEY`

> ⚠️ A `service_role` ignora RLS — **nunca commite essa chave**. Mantenha só em `secrets.toml` (gitignored) ou no dashboard do Streamlit Cloud.

## Rodar local

```powershell
cd "C:\Users\duda\Projetos Claude Schin\Luiz Arrelaro Imóveis\Avaliapp"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configurar secrets (copie e preencha):
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# Edite .streamlit\secrets.toml com SUPABASE_URL, SUPABASE_SERVICE_KEY,
# senha do app e (opcional) chave do Gemini.

streamlit run app.py
```

## Deploy no Streamlit Community Cloud

1. Repo privado no GitHub com o conteúdo desta pasta.
2. Em https://share.streamlit.io: **New app** → conectar repo → branch `main`, arquivo `app.py`.
3. **Advanced settings → Secrets** → cole o conteúdo de `secrets.toml` (mesmo formato TOML).
4. Salvar → Streamlit Cloud builda usando `requirements.txt` e sobe.

## Status do MVP
- [x] Wizard de 5 passos (Identificação → Documentos & fotos → Características → Comparáveis → Cálculo)
- [x] OCR de matrícula/IPTU com aceite suave por campo
- [x] Auto-preenchimento de lat/lng quando o endereço está completo
- [x] Identidade visual real (logo + paleta ciano/preto)
- [x] IA Gemini (redação, análise de comparáveis, OCR, busca de comparáveis)
- [x] PTAM + apresentação em PDF
- [x] Histórico com rascunhos/concluídos no Supabase

## Pendências futuras
- Login multiusuário (hoje é senha única)
- Validação dos graus/fatores contra a NBR 14653 oficial
- Correção monetária por índices (FipeZap/IGMI-R/IVG-R)

Documentação completa do projeto: `..\CLAUDE.md`, `..\HISTORICO-PROJETO.md`, `PESQUISA-AVALIACAO-IMOVEIS.md`.
