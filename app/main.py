"""Painel comparativo de orçamento público: União x Estado x Municípios.

Rodar com: streamlit run app/main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt
import pandas as pd
import streamlit as st

from app.cores import CORES_POR_ENTE, COR_PREVISTO, COR_REALIZADO, ORDEM_ENTES
from extract.config import ENTES_MVP
from extract.rreo import baixar_rreo
from transform.normalizar import normalizar_varios

st.set_page_config(page_title="Orçamento Público: União x Estado x Municípios", layout="wide")


def formatar_reais(valor) -> str:
    if pd.isna(valor):
        return "—"
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(show_spinner="Carregando dados do SICONFI...")
def carregar_dados(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache local) o RREO de todos os entes do MVP e normaliza.

    Retorna a tabela normalizada e a lista de entes sem dado declarado no período.
    A API do SICONFI já teve instabilidades; se uma chamada falhar, o ente entra
    na lista de "sem dado" em vez de derrubar o app inteiro.
    """
    dados_por_ente = {}
    entes_sem_dado = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre)
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}

    tabela = normalizar_varios(dados_por_ente)
    return tabela, entes_sem_dado


st.title("Orçamento Público: União x Estado x Municípios")
st.caption(
    "Comparativo do exercício corrente (previsto x executado) entre os três níveis da federação, "
    "com base no RREO do SICONFI/Tesouro Nacional."
)
st.info(
    "Esta visão cobre apenas o **exercício corrente** (previsão da LOA + execução). "
    "O planejamento plurianual (PPA) de cada ente não está no SICONFI e fica fora do escopo "
    "deste painel — veja o README para detalhes.",
    icon="ℹ️",
)

col_ano, col_bimestre = st.columns(2)
with col_ano:
    exercicio = st.selectbox("Exercício", options=[2024, 2023, 2022], index=0)
with col_bimestre:
    bimestre = st.selectbox(
        "Bimestre (RREO)",
        options=[1, 2, 3, 4, 5, 6],
        index=5,
        help="O RREO é bimestral; o 6º bimestre traz o fechamento do exercício.",
    )

tabela, entes_sem_dado = carregar_dados(exercicio, bimestre)

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

tabela_filtrada = tabela[tabela["ente"].isin(entes_selecionados)]

if tabela_filtrada.empty:
    st.warning("Selecione ao menos um ente para ver os gráficos.")
    st.stop()

escala_entes = alt.Scale(domain=ORDEM_ENTES, range=list(CORES_POR_ENTE.values()))

st.header("Previsto x Executado por ente")
resumo_ente = (
    tabela_filtrada.groupby("ente", as_index=False)[["previsao_inicial", "realizado"]]
    .sum()
    .melt(id_vars="ente", var_name="tipo", value_name="valor")
)
resumo_ente["tipo"] = resumo_ente["tipo"].map(
    {"previsao_inicial": "Previsão inicial", "realizado": "Realizado"}
)

grafico_previsto_executado = (
    alt.Chart(resumo_ente)
    .mark_bar(cornerRadius=4)
    .encode(
        x=alt.X("ente:N", title=None, sort=entes_disponiveis),
        y=alt.Y("valor:Q", title="R$"),
        xOffset=alt.XOffset("tipo:N", sort=["Previsão inicial", "Realizado"]),
        color=alt.Color(
            "tipo:N",
            title=None,
            scale=alt.Scale(domain=["Previsão inicial", "Realizado"], range=[COR_PREVISTO, COR_REALIZADO]),
        ),
        tooltip=[
            alt.Tooltip("ente:N", title="Ente"),
            alt.Tooltip("tipo:N", title="Tipo"),
            alt.Tooltip("valor:Q", title="Valor (R$)", format=",.2f"),
        ],
    )
    .properties(height=380)
)
st.altair_chart(grafico_previsto_executado, width="stretch")

st.header("Despesa por função de governo")
st.caption("Proporção do orçamento realizado de cada ente que foi para cada função de governo.")

totais_por_ente = tabela_filtrada.groupby("ente")["realizado"].sum()
tabela_prop = tabela_filtrada.copy()
tabela_prop["proporcao"] = tabela_prop.apply(
    lambda linha: (linha["realizado"] / totais_por_ente[linha["ente"]]) if totais_por_ente[linha["ente"]] else 0,
    axis=1,
)

funcoes_top = (
    tabela_filtrada.groupby("funcao")["realizado"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .index.tolist()
)
tabela_prop_top = tabela_prop[tabela_prop["funcao"].isin(funcoes_top)]

grafico_funcao = (
    alt.Chart(tabela_prop_top)
    .mark_bar(cornerRadius=4)
    .encode(
        x=alt.X("funcao:N", title=None, sort=funcoes_top),
        y=alt.Y("proporcao:Q", title="% do orçamento realizado", axis=alt.Axis(format="%")),
        xOffset=alt.XOffset("ente:N", sort=entes_disponiveis),
        color=alt.Color("ente:N", title="Ente", scale=escala_entes, sort=entes_disponiveis),
        tooltip=[
            alt.Tooltip("ente:N", title="Ente"),
            alt.Tooltip("funcao:N", title="Função"),
            alt.Tooltip("proporcao:Q", title="% do orçamento", format=".1%"),
            alt.Tooltip("realizado:Q", title="Valor realizado (R$)", format=",.2f"),
        ],
    )
    .properties(height=420)
)
st.altair_chart(grafico_funcao, width="stretch")

st.header("Tabela completa")
tabela_exibicao = tabela_filtrada.copy()
for coluna in ["previsao_inicial", "previsao_atualizada", "realizado"]:
    tabela_exibicao[coluna] = tabela_exibicao[coluna].map(formatar_reais)
st.dataframe(tabela_exibicao, width="stretch", hide_index=True)
