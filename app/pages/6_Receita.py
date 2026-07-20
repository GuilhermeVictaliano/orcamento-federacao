"""Página: Receita realizada — "Quanto o ente faturou".

Mostra a receita arrecadada (realizada) por ente, compara com a despesa
(superávit/déficit orçamentário) e destaca as maiores fontes de receita.
Fonte: RREO-Anexo 01 (Balanço Orçamentário) do SICONFI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import altair as alt
import pandas as pd
import streamlit as st

from app.comum import (
    bimestre_recente_uniao,
    carregar_dados,
    carregar_receita,
    formatar_reais,
)
from app.cores import CORES_POR_ENTE, COR_PREVISTO, COR_REALIZADO, ORDEM_ENTES
from extract.periodos import anos_disponiveis
from transform.receita import totais_receita_por_ente

st.set_page_config(page_title="Receita realizada", layout="wide")

st.title("Quanto o ente faturou — Receita realizada")
st.caption(
    "Receita **arrecadada** (realizada) acumulada até o período, comparada com a despesa. "
    "Fonte: RREO-Anexo 01 (Balanço Orçamentário) do SICONFI/Tesouro Nacional."
)

anos = anos_disponiveis()
col_ano, col_bim = st.columns(2)
with col_ano:
    exercicio = st.selectbox("Exercício", options=anos, index=0)
ultimo_bimestre = bimestre_recente_uniao(exercicio)
with col_bim:
    bimestre = st.selectbox(
        "Bimestre (RREO)",
        options=list(range(1, ultimo_bimestre + 1)),
        index=ultimo_bimestre - 1,
        help="Cada bimestre traz o acumulado desde o início do ano.",
    )

tabela_receita, entes_sem_dado = carregar_receita(exercicio, bimestre)

if entes_sem_dado:
    st.warning("Receita não declarada para: " + ", ".join(entes_sem_dado) + f" no {bimestre}º bimestre de {exercicio}.", icon="⚠️")

if tabela_receita.empty:
    st.error("Nenhuma receita disponível para os filtros selecionados.")
    st.stop()

entes_disponiveis = [n for n in ORDEM_ENTES if n in tabela_receita["ente"].unique()]
entes_sel = st.multiselect("Entes", options=entes_disponiveis, default=entes_disponiveis)
tabela_receita = tabela_receita[tabela_receita["ente"].isin(entes_sel)]
if tabela_receita.empty:
    st.warning("Selecione ao menos um ente.")
    st.stop()

totais_rec = totais_receita_por_ente(tabela_receita).set_index("ente")

# ---------------------------------------------------------------------------
# Receita realizada por ente (cards)
# ---------------------------------------------------------------------------
st.header("Receita realizada por ente")
cards = st.columns(len(totais_rec))
for coluna, (ente, linha) in zip(cards, totais_rec.iterrows()):
    with coluna:
        st.metric(label=ente, value=formatar_reais(linha["realizada"]))
        prev = linha["previsao_atualizada"]
        pct = (linha["realizada"] / prev) if prev else None
        txt = f"{pct:.1%} da previsão atualizada" if pct is not None else "sem previsão"
        st.caption(f"📈 {txt}")

# ---------------------------------------------------------------------------
# Receita x Despesa (superávit / déficit orçamentário)
# ---------------------------------------------------------------------------
st.header("Receita x Despesa (superávit / déficit)")
st.caption(
    "Receita realizada menos despesa liquidada, ambas **exceto intra-orçamentárias** e acumuladas "
    "até o período. Positivo = superávit; negativo = déficit orçamentário no período."
)

tabela_despesa, _, _ = carregar_dados(exercicio, bimestre)
despesa_por_ente = (
    tabela_despesa[tabela_despesa["ente"].isin(entes_sel)]
    .groupby("ente")["realizado"].sum()
)

comparativo = []
for ente in entes_disponiveis:
    if ente not in entes_sel:
        continue
    rec = totais_rec.loc[ente, "realizada"] if ente in totais_rec.index else None
    desp = despesa_por_ente.get(ente)
    if rec is None or desp is None:
        continue
    comparativo.append({"ente": ente, "Receita": rec, "Despesa": desp, "saldo": rec - desp})
comp_df = pd.DataFrame(comparativo)

if not comp_df.empty:
    cards2 = st.columns(len(comp_df))
    for coluna, (_, linha) in zip(cards2, comp_df.iterrows()):
        with coluna:
            saldo = linha["saldo"]
            icone = "🟢" if saldo >= 0 else "🔴"
            rotulo = "Superávit" if saldo >= 0 else "Déficit"
            st.metric(label=linha["ente"], value=formatar_reais(saldo))
            st.caption(f"{icone} {rotulo} orçamentário")

    comp_melt = comp_df.melt(
        id_vars=["ente"], value_vars=["Receita", "Despesa"], var_name="tipo", value_name="valor"
    )
    grafico_rd = (
        alt.Chart(comp_melt)
        .mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("ente:N", title=None, sort=entes_disponiveis),
            y=alt.Y("valor:Q", title="R$"),
            xOffset=alt.XOffset("tipo:N", sort=["Receita", "Despesa"]),
            color=alt.Color(
                "tipo:N", title=None,
                scale=alt.Scale(domain=["Receita", "Despesa"], range=[COR_REALIZADO, COR_PREVISTO]),
            ),
            tooltip=[
                alt.Tooltip("ente:N", title="Ente"),
                alt.Tooltip("tipo:N", title="Tipo"),
                alt.Tooltip("valor:Q", title="Valor (R$)", format=",.2f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(grafico_rd, width="stretch")

# ---------------------------------------------------------------------------
# Maiores fontes de receita (por categoria)
# ---------------------------------------------------------------------------
st.header("Maiores fontes de receita")
st.caption("Composição da receita realizada por categoria econômica.")

ordem_cat = (
    tabela_receita.groupby("categoria")["realizada"].sum().sort_values(ascending=False).index.tolist()
)
escala_entes = alt.Scale(domain=ORDEM_ENTES, range=list(CORES_POR_ENTE.values()))
grafico_cat = (
    alt.Chart(tabela_receita)
    .mark_bar(cornerRadius=4)
    .encode(
        y=alt.Y("categoria:N", title=None, sort=ordem_cat),
        x=alt.X("realizada:Q", title="Receita realizada (R$)"),
        yOffset=alt.YOffset("ente:N", sort=entes_disponiveis),
        color=alt.Color("ente:N", title="Ente", scale=escala_entes, sort=entes_disponiveis),
        tooltip=[
            alt.Tooltip("ente:N", title="Ente"),
            alt.Tooltip("categoria:N", title="Categoria"),
            alt.Tooltip("realizada:Q", title="Realizada (R$)", format=",.2f"),
        ],
    )
    .properties(height=max(320, 30 * len(ordem_cat)))
)
st.altair_chart(grafico_cat, width="stretch")

# ---------------------------------------------------------------------------
# Tabela
# ---------------------------------------------------------------------------
st.header("Tabela de receita por categoria")
tab = tabela_receita.copy()
for c in ["previsao_inicial", "previsao_atualizada", "realizada"]:
    tab[c] = tab[c].map(formatar_reais)
tab = tab.rename(
    columns={
        "ente": "Ente", "nivel": "Nível", "categoria": "Categoria",
        "previsao_inicial": "Previsão inicial (R$)",
        "previsao_atualizada": "Previsão atualizada (R$)",
        "realizada": "Realizada (R$)",
    }
)
st.dataframe(
    tab[["Ente", "Nível", "Categoria", "Previsão inicial (R$)", "Previsão atualizada (R$)", "Realizada (R$)"]],
    width="stretch", hide_index=True,
)
