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

Fonte principal: a **API pública do SICONFI** (Sistema de Informações Contábeis
e Fiscais do Setor Público Brasileiro), mantida pelo Tesouro Nacional —
`https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`. É o que padroniza o
leiaute entre União, estados e municípios e torna a comparação possível.

Usamos o endpoint `/rreo` (Relatório Resumido da Execução Orçamentária), em
vários anexos, cobrindo **de 2015 ao ano corrente**:

| Anexo | O que traz | Página |
|---|---|---|
| Anexo 02 | Despesa por função de governo (previsto x executado) | Home + Período de governo + Saúde fiscal |
| Anexo 01 | Receita realizada (Balanço Orçamentário) | Receita + Saúde fiscal |
| Anexo 07 | Restos a pagar por Poder | Poderes |

Fonte complementar: o **PNCP** (Portal Nacional de Contratações Públicas),
`https://pncp.gov.br/api/consulta/v1/contratos`, para a aba de **Contratos**
(auditoria pelo cidadão). Só permite consulta por CNPJ de órgão.

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

1. **Não cobre o PPA (Plano Plurianual).** O SICONFI cobre a execução
   orçamentária anual (previsão da LOA + execução), agora com série histórica
   de 2015 ao ano corrente. O planejamento de médio prazo (metas de 4 anos por
   programa) fica em fontes separadas por ente — no nível federal, no SIOP; em
   estados e municípios, geralmente só no portal de cada um, muitas vezes em PDF
   não estruturado. Fora do escopo por ora.
2. **Gastos por Poder = restos a pagar.** O RREO não publica a despesa total
   executada por Poder; o único recorte por Poder uniforme entre entes é o de
   restos a pagar (Anexo 07). A aba de Poderes deixa isso explícito.
3. **Precatórios não têm API pública consolidada.** O CNJ só publica painel
   visual. No RREO eles aparecem diluídos em "Encargos Especiais", usado como
   *proxy* de rigidez na aba de Saúde fiscal — não é o estoque exato.
4. **Contratos (PNCP) têm cobertura parcial.** A consulta é por CNPJ de órgão;
   um ente grande tem muitos órgãos e a adesão ao PNCP é parcial. A lista não é
   exaustiva e não carrega função de governo (ligação com despesa é aproximada).
5. **Valores são nominais.** As comparações históricas não são corrigidas por
   inflação — a interface avisa onde isso importa.
6. **A API do SICONFI pode ficar instável.** Já houve manutenções
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
extract/      # SICONFI (rreo, periodos, config) + PNCP (pncp) + cache Parquet
transform/    # normalizar (Anexo 02), receita (01), fiscal (funções),
              #   poderes (07), contratos (PNCP) — formato "longo" -> tabelas
app/
  main.py     # home: despesa por função (visão geral)
  comum.py    # loaders cacheados + helpers compartilhados entre páginas
  cores.py    # paleta dos entes + status de execução
  pages/      # 2_Periodo_de_governo, 3_Saude_fiscal, 4_Poderes,
              #   5_Contratos, 6_Receita
data/raw/     # cache local (gitignored), inclui data/raw/pncp/
tests/        # testes de extract/ e transform/
```

## Ideias de evolução

- Descer ao nível de **subfunção** no Anexo 02 para isolar precatórios
  ("Sentenças Judiciais") dentro de Encargos Especiais.
- Correção por inflação (IPCA) nas séries históricas.
- Execução federal por Poder via Portal da Transparência (complementa Anexo 07).
- Ingestão do PPA por ente e cobertura de mais municípios.
