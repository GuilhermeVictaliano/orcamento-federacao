"""Painel comparativo de orçamento público: União x Estado x Municípios.

Rodar com: streamlit run app/main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt
import pandas as pd
import streamlit as st

from app.comum import (
    bimestre_recente_uniao,
    carregar_dados,
    enriquecer_com_percentuais,
    formatar_pct,
    formatar_reais,
)
from app.cores import CORES_POR_ENTE, COR_PREVISTO, COR_REALIZADO, ORDEM_ENTES, classificar_execucao
from extract.periodos import anos_disponiveis

st.set_page_config(page_title="Orçamento Público: União x Estado x Municípios", layout="wide")


st.title("Orçamento Público: União x Estado x Municípios")
st.caption(
    "Comparativo entre os três níveis da federação (previsto x executado), "
    "com base no RREO do SICONFI/Tesouro Nacional."
)
st.info(
    "Esta visão mostra a **despesa por função de governo** (previsão da LOA + execução) de um "
    "exercício. A série cobre de 2015 ao ano corrente; use as demais páginas na barra lateral "
    "para receita, período de governo, saúde fiscal, Poderes e contratos.",
    icon="ℹ️",
)

modo_periodo = st.radio(
    "Período de análise",
    ["Ano completo (acumulado)", "Bimestre específico"],
    horizontal=True,
    help="O RREO é bimestral e cada bimestre já traz o valor acumulado desde o início do ano. "
    "\"Ano completo\" usa o acumulado até o último bimestre publicado do exercício.",
)

anos = anos_disponiveis()
col_ano, col_bimestre = st.columns(2)
with col_ano:
    exercicio = st.selectbox("Exercício", options=anos, index=0)

# O ano corrente ainda não fechou o 6º bimestre: usar o último publicado como teto.
ultimo_bimestre = bimestre_recente_uniao(exercicio)
with col_bimestre:
    if modo_periodo == "Bimestre específico":
        opcoes_bimestre = list(range(1, ultimo_bimestre + 1))
        bimestre = st.selectbox("Bimestre (RREO)", options=opcoes_bimestre, index=len(opcoes_bimestre) - 1)
    else:
        bimestre = ultimo_bimestre
        rotulo = "6º bimestre (fechamento)" if ultimo_bimestre == 6 else f"{ultimo_bimestre}º bimestre (último publicado)"
        st.caption(f"Usando o acumulado até o {rotulo}.")

tabela, entes_sem_dado, metadados_entes = carregar_dados(exercicio, bimestre)

if entes_sem_dado:
    st.warning(
        "Dado não declarado para: " + ", ".join(entes_sem_dado) + f" no {bimestre}º bimestre de {exercicio}.",
        icon="⚠️",
    )

if tabela.empty:
    st.error("Nenhum dado disponível para os filtros selecionados.")
    st.stop()

entes_disponiveis = [nome for nome in ORDEM_ENTES if nome in tabela["ente"].unique()]
entes_selecionados = st.multiselect("Entes", options=entes_disponiveis, default=entes_disponiveis)

tabela_entes = tabela[tabela["ente"].isin(entes_selecionados)]

if tabela_entes.empty:
    st.warning("Selecione ao menos um ente para ver os gráficos.")
    st.stop()

escala_entes = alt.Scale(domain=ORDEM_ENTES, range=list(CORES_POR_ENTE.values()))

# ---------------------------------------------------------------------------
# Previsto x Executado por ente
# ---------------------------------------------------------------------------
st.header("Previsto x Executado por ente")
st.caption(
    "**Previsão inicial** = orçamento aprovado na LOA para o ano. "
    "**Realizado** = despesas **liquidadas** (bem/serviço já entregue) até o período selecionado — "
    "não é apenas o valor empenhado/reservado."
)

resumo_ente = tabela_entes.groupby("ente", as_index=False)[
    ["previsao_inicial", "previsao_atualizada", "realizado"]
].sum()
resumo_ente["pct_execucao"] = resumo_ente.apply(
    lambda linha: (linha["realizado"] / linha["previsao_atualizada"]) if linha["previsao_atualizada"] else None,
    axis=1,
)
cards = st.columns(len(resumo_ente))
for coluna, (_, linha) in zip(cards, resumo_ente.iterrows()):
    status = classificar_execucao(linha["pct_execucao"])
    with coluna:
        st.metric(label=linha["ente"], value=formatar_pct(linha["pct_execucao"]))
        st.caption(f"{status['icone']} {status['rotulo']} · % de execução (realizado / previsão atualizada)")

resumo_melt = resumo_ente.melt(
    id_vars=["ente", "pct_execucao"],
    value_vars=["previsao_inicial", "realizado"],
    var_name="tipo",
    value_name="valor",
)
resumo_melt["tipo"] = resumo_melt["tipo"].map({"previsao_inicial": "Previsão inicial", "realizado": "Realizado"})

grafico_previsto_executado = (
    alt.Chart(resumo_melt)
    .mark_bar(cornerRadius=4)
    .encode(
        x=alt.X("ente:N", title=None, sort=entes_disponiveis),
        y=alt.Y("valor:Q", title="R$"),
        xOffset=alt.XOffset("tipo:N", sort=["Previsão inicial", "Realizado"]),
        color=alt.Color(
            "tipo:N",
            title="Tipo de valor",
            scale=alt.Scale(domain=["Previsão inicial", "Realizado"], range=[COR_PREVISTO, COR_REALIZADO]),
        ),
        tooltip=[
            alt.Tooltip("ente:N", title="Ente"),
            alt.Tooltip("tipo:N", title="Tipo"),
            alt.Tooltip("pct_execucao:Q", title="% de execução", format=".1%"),
            alt.Tooltip("valor:Q", title="Valor (R$)", format=",.2f"),
        ],
    )
    .properties(height=380)
)
st.altair_chart(grafico_previsto_executado, width="stretch")

# ---------------------------------------------------------------------------
# Filtros (aplicam-se à seção de função de governo e à tabela completa)
# ---------------------------------------------------------------------------
st.header("Filtros")
col_busca, col_funcoes, col_operador = st.columns([1.2, 1.6, 1])
with col_busca:
    busca_funcao = st.text_input("Buscar função por nome", placeholder="ex.: saúde")
with col_funcoes:
    funcoes_disponiveis = sorted(tabela_entes["funcao"].unique())
    funcoes_selecionadas = st.multiselect("Função de governo", options=funcoes_disponiveis)
with col_operador:
    operador_valor = st.selectbox("Filtrar por valor realizado", ["Sem filtro", "Maior que", "Menor que", "Entre"])

limite_min = limite_max = None
if operador_valor == "Maior que":
    limite_min = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=1_000_000.0, format="%.2f")
elif operador_valor == "Menor que":
    limite_max = st.number_input("Valor máximo (R$)", min_value=0.0, value=0.0, step=1_000_000.0, format="%.2f")
elif operador_valor == "Entre":
    col_min, col_max = st.columns(2)
    with col_min:
        limite_min = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=1_000_000.0, format="%.2f")
    with col_max:
        limite_max = st.number_input("Valor máximo (R$)", min_value=0.0, value=1_000_000_000.0, step=1_000_000.0, format="%.2f")

tabela_funcoes = tabela_entes.copy()
if busca_funcao:
    tabela_funcoes = tabela_funcoes[tabela_funcoes["funcao"].str.contains(busca_funcao, case=False, na=False)]
if funcoes_selecionadas:
    tabela_funcoes = tabela_funcoes[tabela_funcoes["funcao"].isin(funcoes_selecionadas)]
if operador_valor == "Maior que" and limite_min is not None:
    tabela_funcoes = tabela_funcoes[tabela_funcoes["realizado"] > limite_min]
elif operador_valor == "Menor que" and limite_max is not None:
    tabela_funcoes = tabela_funcoes[tabela_funcoes["realizado"] < limite_max]
elif operador_valor == "Entre" and limite_min is not None and limite_max is not None:
    tabela_funcoes = tabela_funcoes[tabela_funcoes["realizado"].between(limite_min, limite_max)]

if tabela_funcoes.empty:
    st.warning("Nenhuma função de governo corresponde aos filtros selecionados.")
    st.stop()

# % do orçamento sempre relativo ao total do ente (não ao subconjunto filtrado),
# para que o número continue significando "fatia do orçamento total".
totais_por_ente = tabela_entes.groupby("ente")["realizado"].sum()
tabela_funcoes_enriquecida = enriquecer_com_percentuais(tabela_funcoes, totais_por_ente)

# ---------------------------------------------------------------------------
# Despesa por função de governo (gráfico horizontal)
# ---------------------------------------------------------------------------
st.header("Despesa por função de governo")
st.caption("Proporção do orçamento realizado de cada ente que foi para cada função de governo.")

ordem_funcoes = (
    tabela_funcoes_enriquecida.groupby("funcao")["realizado"]
    .sum()
    .sort_values(ascending=False)
    .head(15)
    .index.tolist()
)
tabela_funcoes_grafico = tabela_funcoes_enriquecida[tabela_funcoes_enriquecida["funcao"].isin(ordem_funcoes)]

grafico_funcao = (
    alt.Chart(tabela_funcoes_grafico)
    .mark_bar(cornerRadius=4)
    .encode(
        y=alt.Y("funcao:N", title=None, sort=ordem_funcoes),
        x=alt.X("proporcao:Q", title="% do orçamento realizado", axis=alt.Axis(format="%")),
        yOffset=alt.YOffset("ente:N", sort=entes_disponiveis),
        color=alt.Color("ente:N", title="Ente", scale=escala_entes, sort=entes_disponiveis),
        tooltip=[
            alt.Tooltip("ente:N", title="Ente"),
            alt.Tooltip("funcao:N", title="Função"),
            alt.Tooltip("proporcao:Q", title="% do orçamento", format=".1%"),
            alt.Tooltip("realizado:Q", title="Valor realizado (R$)", format=",.2f"),
        ],
    )
    .properties(height=max(320, 32 * len(ordem_funcoes)))
)
st.altair_chart(grafico_funcao, width="stretch")

# ---------------------------------------------------------------------------
# Tabela completa
# ---------------------------------------------------------------------------
st.header("Tabela completa")

tabela_exibicao = tabela_funcoes_enriquecida.copy()
tabela_exibicao["Status"] = tabela_exibicao["status_icone"] + " " + tabela_exibicao["status_rotulo"]
tabela_exibicao["% do orçamento do ente"] = tabela_exibicao["proporcao"].map(formatar_pct)
tabela_exibicao["% de execução"] = tabela_exibicao["pct_execucao"].map(formatar_pct)
for coluna in ["previsao_inicial", "previsao_atualizada", "realizado"]:
    tabela_exibicao[coluna] = tabela_exibicao[coluna].map(formatar_reais)

tabela_exibicao = tabela_exibicao.rename(
    columns={
        "ente": "Ente",
        "nivel": "Nível",
        "funcao": "Função",
        "previsao_inicial": "Previsão inicial (R$)",
        "previsao_atualizada": "Previsão atualizada (R$)",
        "realizado": "Realizado (R$)",
    }
)

colunas_finais = [
    "Status",
    "Ente",
    "Nível",
    "Função",
    "% do orçamento do ente",
    "% de execução",
    "Previsão inicial (R$)",
    "Previsão atualizada (R$)",
    "Realizado (R$)",
]
st.dataframe(tabela_exibicao[colunas_finais], width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Metadados da base de dados
# ---------------------------------------------------------------------------
with st.expander("📋 Sobre esta base de dados (metadados e trajetória)"):
    total_linhas_brutas = sum(m["linhas_brutas"] for m in metadados_entes)
    periodo_texto = (
        f"acumulado até o 6º bimestre (ano completo) de {exercicio}"
        if modo_periodo != "Bimestre específico"
        else f"{bimestre}º bimestre de {exercicio}"
    )
    st.markdown(
        f"""
**De onde veio → como foi tratado → como está sendo mostrado**

1. **Fonte primária:** API pública do SICONFI (Sistema de Informações Contábeis e Fiscais do Setor
   Público Brasileiro), Tesouro Nacional — endpoint `/rreo`, Anexo 02 (despesa por função de governo).
   `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo`
2. **Extração:** dados baixados por ente/exercício/bimestre e salvos em cache local (Parquet) —
   ver tabela de sincronização abaixo.
3. **Transformações aplicadas** (`transform/normalizar.py`):
   - Filtro do rótulo `Total das Despesas Exceto Intra-Orçamentárias` (exclui transferências
     internas do próprio ente, que duplicariam valores).
   - Filtro das 28 funções oficiais de governo (Portaria MOG nº 42/1999), descartando linhas
     de subfunção que vêm misturadas na mesma coluna da API.
   - Pivot do formato "longo" da API (`conta` × `coluna` × `valor`) para uma linha por função,
     com as colunas `previsao_inicial`, `previsao_atualizada` e `realizado`.
   - "Realizado" usa despesas **liquidadas** (não apenas empenhadas) até o período.
4. **Apresentação:** valores agregados por ente e por função, com percentuais calculados sobre
   o total do orçamento do ente (não sobre o subconjunto filtrado na tela).

**Período abrangido:** exercício {exercicio}, {periodo_texto}.

**Registros processados:** {total_linhas_brutas:,} linhas brutas baixadas da API → {len(tabela):,}
linhas na tabela normalizada (uma linha por ente × função de governo).

**Filtros/exclusões realizadas:** despesas intra-orçamentárias e subfunções (item 3 acima).
{"Sem dado declarado neste período: " + ", ".join(entes_sem_dado) + "." if entes_sem_dado else "Todos os entes do MVP tinham dado declarado neste período."}
        """.strip()
    )

    st.markdown("**Última sincronização por ente (data do cache local):**")
    tabela_sync = pd.DataFrame(metadados_entes)
    tabela_sync["atualizado_em"] = tabela_sync["atualizado_em"].apply(
        lambda dt: dt.strftime("%d/%m/%Y %H:%M") if pd.notna(dt) else "— (sem cache)"
    )
    tabela_sync = tabela_sync.rename(
        columns={"ente": "Ente", "linhas_brutas": "Linhas brutas", "atualizado_em": "Última sincronização"}
    )
    st.dataframe(tabela_sync, width="stretch", hide_index=True)
