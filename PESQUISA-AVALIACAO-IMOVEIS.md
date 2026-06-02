# Pesquisa Técnica — Avaliação de Imóveis no Brasil (insumo para o Avaliapp)

> Referência técnica do projeto **Avaliapp**. Pesquisa com fontes brasileiras recentes (2024–2026).
> ⚠️ Valores de graus/precisão e fatores variam entre fontes secundárias — **validar contra a NBR 14653 oficial (paga) e o Manual de Avaliação de Imóveis da União 2024 (gratuito)** antes de fixar no código.

---

## 1. Normas e regulamentação

**NBR 14653 (ABNT)** — rege avaliação de bens. Partes: 1 (procedimentos gerais), **2 (imóveis urbanos — central para o app)**, 3 (rurais), 4 (empreendimentos), 5 (máquinas/instalações), 6 (recursos naturais), 7 (patrimônios históricos).

**Graus de fundamentação (I/II/III)** e **de precisão** (só no método comparativo). Referências (método comparativo, tratamento científico):

| Grau | Dados mínimos | Tratamento | Uso típico |
|------|---------------|-----------|------------|
| I (expedito) | ~6 | inferência não obrigatória | consulta preliminar |
| II (normal) | ~10 | regressão/inferência | financiamento, ITBI, acordos |
| III (rigoroso) | ~16 (na prática 40–50) | múltiplas variáveis + análise de resíduos | desapropriação, litígio |

- Métodos custo/evolutivo/involutivo recebem só grau de **fundamentação** (não de precisão).
- Atualidade dos dados: urbanos ~12 meses; rurais ~24 meses.

**PTAM vs. Laudo de Engenharia (decisão-chave do projeto):**

| Aspecto | **PTAM** | **Laudo (Engenharia)** |
|---------|----------|------------------------|
| Profissional | Corretor **CRECI** | Engenheiro/Arquiteto **CREA/CAU** |
| Base legal | Lei 6.530/78; Res. COFECI 957/2006 e **1.066/2007** | NBR 14653 + atribuição de engenharia |
| Responsabilidade | (sem ART) | **ART** no CREA |
| Uso | negociação, leilão, garantia, base de preço | judicial, bancário, fiscal, desapropriação |

- O **corretor pode emitir PTAM** (Res. COFECI 1.066/2007). Não exige CNAI para PTAM simples.
- **CNAI** (Cadastro Nacional de Avaliadores Imobiliários) = credencial **opcional** do corretor (selo de credibilidade). **CREA/CAU** é do engenheiro/arquiteto — não confundir.
- ➜ O Avaliapp gera **PTAM**, referenciando NBR 14653-2; **nunca** ART/laudo de engenharia. Prever campo para nº CNAI quando aplicável.

---

## 2. Métodos de avaliação

**Comparativo Direto de Dados de Mercado (MCDDM)** — o mais usado. Dois tratamentos:
- **Por fatores (homogeneização):** ajusta cada comparável por fatores multiplicativos. Mais simples, mais subjetivo, graus menores. **→ adotado no MVP.**
- **Científico (inferência/regressão linear múltipla):** modela o mercado com validação estatística (t/F, R², resíduos). Atinge graus II/III. (Evolução futura.)

**Outros métodos:**
- **Evolutivo:** terreno (comparativo) + benfeitorias (custo). Casas/imóveis construídos sem comparável direto.
- **Involutivo:** simula aproveitamento de terreno/gleba descontando custos. Glebas urbanizáveis, incorporação.
- **Renda (capitalização):** valor pela renda gerada (aluguel/fluxo). Comerciais, galpões, hotéis.
- **Custo:** custo de reprodução depreciado (SINAPI/SINDUSCON/CUB). Benfeitorias e imóveis especiais.

**Homogeneização e fatores (limites encontrados — confirmar na norma):**
- Fator oferta/fonte: 0,80–1,20; indeterminado → 0,90 (~10% de desconto do anúncio).
- Fator localização/transposição: FL = IFA/IFD (índices fiscais), com limites.
- Fatores de forma do terreno (testada, profundidade, área, esquina).
- Conservação: **Ross-Heidecke** (Foc = R + K(1−R)).
- Padrão/acabamento: SINDUSCON/SINAPI/CUB.
- **Campo de arbítrio:** ±15% em torno da tendência central, com justificativa.
- Saneamento: mínimo 3 elementos; descarte de discrepantes (~±30% da média).
- Fatores não valem fora do campo de aplicação (tipologia/região/validade).

---

## 3. Dados necessários (campos por tipo de imóvel)

**Comuns:** tipo, matrícula (RI), inscrição IPTU, CEP, endereço, geolocalização; documentos (matrícula, escritura, IPTU, planta, certidões, ônus); localização/entorno (bairro, infraestrutura, perfil, acessos); finalidade e data de referência.

- **Apartamento:** área privativa/comum/total; andar; quartos/suítes; banheiros; vagas; varanda; idade; padrão; conservação (Ross-Heidecke); condomínio; face/sol; elevadores; lazer.
- **Casa:** área terreno/construída; pavimentos; quartos/suítes/banheiros; vagas; idade; padrão; conservação; topografia; recuos; piscina/benfeitorias.
- **Terreno/lote:** área; testada; profundidade; topografia; formato; esquina; zoneamento (coef. aproveitamento, taxa ocupação, gabarito); infraestrutura; uso permitido.
- **Comercial:** área útil; pé-direito; testada/visibilidade; fluxo; vagas; potencial de renda (R$/m²); padrão; (galpão: docas, capacidade de piso, acessos).
- **Rural (NBR 14653-3):** área (ha); capacidade de uso do solo; benfeitorias reprodutivas/não; recursos hídricos; culturas/pastagens; acesso; aptidão; georreferenciamento (CAR/CCIR).

**Variáveis de maior impacto:** localização, área, padrão construtivo, conservação, idade, vagas, infraestrutura do entorno, andar (apto), vizinhança. (IGMI-R usa >40 variáveis.)

---

## 4. Estrutura de um PTAM (13 seções)
1. Capa (título + nº). 2. Identificação do profissional (CRECI, CNAI, contato). 3. Solicitante/cliente. 4. Objeto e **finalidade**. 5. **Pressupostos, ressalvas e condições limitantes**. 6. Caracterização do imóvel (endereço, matrícula, fotos). 7. Região/entorno. 8. **Metodologia** (método + ref. NBR 14653-2 + tratamento). 9. **Pesquisa de mercado** (tabela de comparáveis + fontes). 10. **Homogeneização/cálculos** (fatores, saneamento, campo de arbítrio). 11. Gráfico comparativo. 12. **Conclusão de valor** (valor, intervalo, grau atingido, data). 13. **Anexos e assinatura** (CRECI; ART só em laudo de engenharia).

---

## 5. Fontes de dados de mercado

**Portais (comparáveis):** Grupo OLX (ZAP, VivaReal, OLX, Lugar Certo) — há portal de integração p/ desenvolvedores (leads, não feed aberto de preços); coleta de comparáveis na prática via scrapers de terceiros (ex.: Apify) — **atenção a Termos de Uso/legalidade**. Imovelweb / Mercado Livre Imóveis idem.

**Índices (tendência/atualização monetária):**
- **FipeZap** (Fipe) — venda e locação, baseado nos portais do Grupo OLX.
- **IGMI-R** (FGV/IBRE + Abecip) — hedônico, baseado em laudos de financiamento (>40 variáveis); variante comercial IGMI-C.
- **IVG-R** (Banco Central) — valores de garantia de financiados; via SGS/BCB.
- Acesso programático: pacote R **`realestatebr`** + API SGS/BCB.

**Públicos:** Planta Genérica de Valores (PGV)/IPTU da prefeitura (varia por município, sem padrão nacional de API); cartórios/ONR-SERP (acesso documental/pago, sem API aberta confirmada); **SINAPI** (Caixa/IBGE) e **CUB** (SINDUSCON) para custos.

---

## 6. Como a IA apoia
- **AVM** (estimativa automática) p/ pré-precificação e checagem — não substitui o PTAM assinado.
- Seleção/análise de comparáveis e detecção de outliers.
- Modelagem estatística assistida (regressão hedônica, validação, grau).
- **OCR/extração** de matrícula, IPTU, escritura, planta → autopreenche campos.
- **Redação automática** das seções do PTAM a partir dos dados estruturados (maior ganho de tempo).
- Geoanálise (POIs, infraestrutura, zoneamento).
- Princípio: IA é **apoio**; manter "humano no circuito" e registrar fontes/comparáveis (auditabilidade).

---

## 7. Concorrentes / ferramentas (Brasil)
- **AVMs:** Urbit AVM, Kognita AVM, Valor Ideal, Lystos.
- **Software de laudo/inferência:** INFER (Plus), Laudo Master (c/ IA), Caxias IA (PTAM com IA p/ corretores), Pelli Sistemas.
- **Adjacentes:** QuintoAndar (precificação interna por IA); bancos/fintechs com AVM próprio.

---

## Fontes principais
- Manual de Avaliação de Imóveis da União 2024 (gov.br) — fonte primária gratuita.
- caxiasia.com (NBR 14653, como fazer PTAM); cvcrm.com.br; cursoavalia.com; mkavaliacoesimobiliarias.com.br; grupocpcon.com; guiadaengenharia.com; inteligenciaurbana.org; manualdepericias.com.br; leadconsultoria.com.
- Índices: fipe.org.br (FipeZap); anbima.com.br/abecip (IGMI-R); SGS/BCB (IVG-R); restateinsight.com (pacote realestatebr).
- IA: esattoavaliacoes.com.br; lageportilhojardim.com.br; mercadoeconsumo.com.br (QuintoAndar).

> Itens não confirmados: API pública padronizada para PGV/IPTU municipal e cartórios (ONR/SERP) — disponibilidade varia, exige verificação caso a caso.
