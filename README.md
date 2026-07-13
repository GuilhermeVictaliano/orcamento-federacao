# Orçamento Federação

Painel web que compara o orçamento público dos três níveis da federação
brasileira (União, um estado e alguns municípios) lado a lado, de forma
visual e navegável.

## Como rodar

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app/main.py
```

Rodar os testes:

```powershell
.\.venv\Scripts\pytest
```

Na primeira execução (ou quando não houver cache), o app baixa os dados
diretamente da API do SICONFI — pode levar alguns segundos. Nas execuções
seguintes ele lê do cache local em `data/raw/`.

## Deploy em produção (Streamlit Community Cloud)

Escolhido em vez de Vercel: o Streamlit precisa de um processo Python de
longa duração com WebSocket persistente, o que não roda bem no modelo
serverless da Vercel. O Streamlit Community Cloud é feito para este stack
exato — puxa direto do GitHub, gratuito, sem reescrever nada.

1. Acesse `https://share.streamlit.io` e faça login com a conta GitHub
   `GuilhermeVictaliano` (o mesmo login usado no `gh auth status`).
2. Clique em **"New app"** → **"Deploy a public app from a private GitHub repo"**
   (o repositório pode continuar privado; só o app publicado fica público).
3. Autorize o Streamlit a acessar o repositório `orcamento-federacao`
   quando solicitado (instala um GitHub App com acesso só a este repo).
4. Preencha:
   - **Repository:** `GuilhermeVictaliano/orcamento-federacao`
   - **Branch:** `master`
   - **Main file path:** `app/main.py`
5. Clique em **"Deploy"**. O primeiro carregamento demora mais (baixa os 5
   entes da API do SICONFI do zero, sem cache — o deploy não leva o
   conteúdo de `data/raw/`, que é gitignored).
6. O app fica público em uma URL `https://<algo>.streamlit.app`. Free tier:
   o app "dorme" após um tempo sem acesso e acorda no primeiro clique.

Não há segredos/API keys a configurar — a API do SICONFI é pública e sem
autenticação.

## De onde vêm os dados

Fonte única: a **API pública do SICONFI** (Sistema de Informações Contábeis
e Fiscais do Setor Público Brasileiro), mantida pelo Tesouro Nacional —
`https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`. É o que padroniza o
leiaute entre União, estados e municípios e torna a comparação possível.

Usamos o endpoint `/rreo` (Relatório Resumido da Execução Orçamentária,
Anexo 02 — despesa por função de governo), que traz previsão orçamentária e
execução no mesmo relatório, bimestral.

**Atenção ao formato real da resposta:** a API devolve os dados em formato
"longo" — cada linha combina `conta` (função/subfunção de governo) × `coluna`
(o tipo de valor, ex. "DOTAÇÃO INICIAL", "DESPESAS LIQUIDADAS ATÉ O BIMESTRE")
× `valor`. Não existe uma linha por conta já com `previsao_inicial`,
`previsao_atualizada` e `realizado` em colunas separadas — isso é construído
na camada de transformação (`transform/normalizar.py`), que:

- filtra só o rótulo `Total das Despesas Exceto Intra-Orçamentárias` (para não
  contar duas vezes transferências internas do próprio ente);
- filtra só linhas de **função** de governo (as 28 funções oficiais da
  Portaria MOG nº 42/1999), descartando as subfunções que aparecem misturadas
  na mesma coluna;
- usa **despesas liquidadas** (não empenhadas) como medida de "realizado" —
  é o padrão técnico de execução orçamentária, pois exige que o bem/serviço já
  tenha sido entregue, não apenas reservado no orçamento.

Entes cobertos no MVP (códigos IBGE em `extract/config.py`):

| Ente | Nível | id_ente |
|---|---|---|
| União | federal | 1 |
| Estado de São Paulo | estadual | 35 |
| São Paulo (capital) | municipal | 3550308 |
| Sorocaba | municipal | 3552205 |
| Campinas | municipal | 3509502 |

## Limitações conhecidas

1. **Não cobre o PPA (Plano Plurianual).** O SICONFI só cobre o **exercício
   corrente** (previsão da LOA do ano + execução). O planejamento de médio
   prazo (metas de 4 anos por programa) fica em fontes separadas por ente —
   no nível federal, no SIOP; em estados e municípios, geralmente só no
   portal de cada um, muitas vezes em PDF não estruturado. Isso é fase 2,
   fora do escopo deste MVP. A interface deixa isso explícito.
2. **A API do SICONFI pode ficar instável.** Já houve manutenções
   emergenciais no Tesouro. Por isso toda consulta é persistida em cache
   local (Parquet, em `data/raw/`) e o app lê do cache — se a API cair, o
   app continua funcionando com o último dado baixado. Se um ente falhar e
   não houver cache, ele aparece na interface como "dado não declarado" em
   vez de quebrar o app.
3. **Nem todo município declara em dia.** Municípios pequenos podem ter
   dados faltando ou atrasados para um bimestre — tratado da mesma forma
   acima.

## Estrutura do projeto

```
extract/      # chamadas à API do SICONFI + cache local em Parquet
transform/    # normalização do formato "longo" da API numa tabela comparável
app/          # painel Streamlit (seletores, gráficos, tabela)
data/raw/     # cache local (gitignored)
tests/        # testes de extract/ e transform/
```

## Fase 2 (não implementada, só prevista)

- Ingestão do PPA por ente (raspagem dos portais estaduais/municipais,
  tratamento de PDF).
- Série histórica multi-ano via [Base dos Dados](https://basedosdados.org/)
  (BigQuery), para cruzamentos de longo prazo sem depender só da API do
  Tesouro.
- Cobertura de mais municípios.
