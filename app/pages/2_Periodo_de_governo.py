"""Página: Período de governo (mandatos de quatro anos).

Analisa a série histórica de um ente agrupada por mandato:
- Tendência AO LONGO do tempo (colorida por mandato).
- Tendência DENTRO do mandato (anos 1→4 sobrepostos para comparar a trajetória).
- Comparação ENTRE mandatos.

Valores nominais (não ajustados por inflação). O ano corrente é parcial.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import altair as alt
import pandas as pd
import streamlit as st

from app.comum import formatar_reais, serie_anual_despesa, serie_anual_receita
from app.cores import ORDEM_ENTES
from extract.periodos import anos_disponiveis, mandato_do_ano, rotulo_mandato

st.set_page_config(page_title="Período de governo", layout="wide")

st.title("Período de governo — mandatos de quatro anos")
st.caption(
    "Como a despesa/receita de um ente evolui dentro de cada mandato e entre mandatos. "
    "União e estados seguem um calendário eleitoral; municípios, outro (deslocado em 2 anos)."
)

col_ente, col_metrica = st.columns(2)
with col_ente:
    ente = st.selectbox("Ente", options=ORDEM_ENTES, index=0)
with col_metrica:
    metrica = st.radio("Métrica", ["Despesa realizada", "Receita realizada"], horizontal=True)

anos = tuple(anos_disponiveis())

if metrica == "Despesa realizada":
    serie = serie_anual_despesa(anos)
    coluna_valor = "realizado"
else:
    serie = serie_anual_receita(anos)
    coluna_valor = "realizada"

serie_ente = serie[serie["ente"] == ente].copy()
if serie_ente.empty:
    st.error("Sem dados para este ente na série histórica.")
    st.stop()

nivel = serie_ente["nivel"].iloc[0]
serie_ente["mandato"] = serie_ente["ano"].map(
    lambda a: rotulo_mandato(*mandato_do_ano(a, nivel)) if mandato_do_ano(a, nivel) else "—"
)
serie_ente["ano_no_mandato"] = serie_ente["ano"].map(
    lambda a: (a - mandato_do_ano(a, nivel)[0] + 1) if mandato_do_ano(a, nivel) else None
)
serie_ente["valor"] = serie_ente[coluna_valor]
serie_ente = serie_ente.sort_values("ano")

tem_parcial = bool(serie_ente["parcial"].any())

st.info(
    "⚠️ Valores **nominais** (não corrigidos por inflação) — comparações entre anos distantes "
    "sofrem efeito de preços."
    + (" O ano corrente é **parcial** (últimos bimestres ainda não publicados) e aparece destacado."
       if tem_parcial else ""),
    icon="ℹ️",
)

# ---------------------------------------------------------------------------
# 1. Tendência ao longo do tempo (colorida por mandato)
# ---------------------------------------------------------------------------
st.header(f"{metrica} ao longo do tempo — {ente}")
st.caption("Cada cor é um mandato. Pontos vazados = ano parcial (ainda em execução).")

base = alt.Chart(serie_ente)
linha_tempo = (
    base.mark_line(point=False)
    .encode(
        x=alt.X("ano:O", title="Ano"),
        y=alt.Y("valor:Q", title="R$"),
        color=alt.Color("mandato:N", title="Mandato"),
        detail="mandato:N",
    )
)
pontos_tempo = (
    base.mark_point(size=90, filled=True)
    .encode(
        x="ano:O",
        y="valor:Q",
        color=alt.Color("mandato:N", title="Mandato"),
        fill=alt.condition("datum.parcial", alt.value("white"), alt.Color("mandato:N", legend=None)),
        tooltip=[
            alt.Tooltip("ano:O", title="Ano"),
            alt.Tooltip("mandato:N", title="Mandato"),
            alt.Tooltip("valor:Q", title=metrica + " (R$)", format=",.2f"),
            alt.Tooltip("parcial:N", title="Parcial?"),
        ],
    )
)
st.altair_chart((linha_tempo + pontos_tempo).properties(height=380), width="stretch")

# ---------------------------------------------------------------------------
# 2. Tendência DENTRO do mandato (anos 1→4 sobrepostos)
# ---------------------------------------------------------------------------
st.header("Tendência dentro do mandato")
st.caption(
    "Cada linha é um mandato, alinhado pelo ano do mandato (1º ao 4º). "
    "Sobrepor as linhas revela se o padrão de gasto/arrecadação se repete a cada governo."
)
dentro = serie_ente[serie_ente["ano_no_mandato"].notna()]
grafico_dentro = (
    alt.Chart(dentro)
    .mark_line(point=True)
    .encode(
        x=alt.X("ano_no_mandato:O", title="Ano do mandato (1º → 4º)"),
        y=alt.Y("valor:Q", title="R$"),
        color=alt.Color("mandato:N", title="Mandato"),
        tooltip=[
            alt.Tooltip("mandato:N", title="Mandato"),
            alt.Tooltip("ano_no_mandato:O", title="Ano do mandato"),
            alt.Tooltip("ano:O", title="Ano civil"),
            alt.Tooltip("valor:Q", title=metrica + " (R$)", format=",.2f"),
        ],
    )
    .properties(height=380)
)
st.altair_chart(grafico_dentro, width="stretch")

# ---------------------------------------------------------------------------
# 3. Comparação entre mandatos + variação intra-mandato
# ---------------------------------------------------------------------------
st.header("Comparação entre mandatos")

resumo = []
for mandato, grupo in serie_ente.groupby("mandato"):
    if mandato == "—":
        continue
    g = grupo.sort_values("ano")
    completos = g[~g["parcial"]]
    media = completos["valor"].mean() if not completos.empty else g["valor"].mean()
    primeiro = g.iloc[0]["valor"]
    ultimo = g.iloc[-1]["valor"]
    variacao = (ultimo / primeiro - 1) if primeiro else None
    resumo.append(
        {
            "Mandato": mandato,
            "Anos com dado": len(g),
            "Média anual (R$)": media,
            f"1º ano ({int(g.iloc[0]['ano'])})": primeiro,
            f"Último ano ({int(g.iloc[-1]['ano'])})": ultimo,
            "Variação 1º→último": variacao,
        }
    )
resumo_df = pd.DataFrame(resumo)

if not resumo_df.empty:
    cards = st.columns(len(resumo_df))
    for coluna, (_, linha) in zip(cards, resumo_df.iterrows()):
        with coluna:
            var = linha["Variação 1º→último"]
            st.metric(
                label=linha["Mandato"],
                value=formatar_reais(linha["Média anual (R$)"]),
                delta=(f"{var:+.1%} (1º→último)" if var is not None else None),
            )
            st.caption("média anual do mandato")

    grafico_entre = (
        alt.Chart(serie_ente[serie_ente["mandato"] != "—"])
        .mark_bar(cornerRadius=3)
        .encode(
            x=alt.X("mandato:N", title="Mandato"),
            y=alt.Y(f"mean(valor):Q", title="Média anual (R$)"),
            color=alt.Color("mandato:N", title="Mandato", legend=None),
            tooltip=[alt.Tooltip("mandato:N"), alt.Tooltip("mean(valor):Q", title="Média anual (R$)", format=",.2f")],
        )
        .properties(height=320)
    )
    st.altair_chart(grafico_entre, width="stretch")

    tabela = resumo_df.copy()
    for c in tabela.columns:
        if "R$" in c or c.startswith("1º") or c.startswith("Último"):
            tabela[c] = tabela[c].map(formatar_reais)
    tabela["Variação 1º→último"] = resumo_df["Variação 1º→último"].map(
        lambda v: f"{v:+.1%}" if v is not None else "—"
    )
    st.dataframe(tabela, width="stretch", hide_index=True)
