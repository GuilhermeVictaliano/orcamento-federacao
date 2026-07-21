"""Página: Poderes — restos a pagar por Poder (RREO-Anexo 07).

⚠️ Escopo honesto: o RREO bimestral NÃO quebra a despesa total executada por Poder.
O único recorte por Poder uniforme entre os entes é o de **restos a pagar** —
obrigações de exercícios anteriores ainda não quitadas. É um bom termômetro de
"herança de contas a pagar" de cada Poder, mas não é o gasto total do Poder.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import altair as alt
import streamlit as st

from app.comum import bimestre_recente_uniao, botao_download_csv, carregar_restos_poder, formatar_reais
from app.cores import CORES_POR_ENTE, ORDEM_ENTES
from extract.periodos import anos_disponiveis
from transform.poderes import ORDEM_PODERES

st.set_page_config(page_title="Poderes", layout="wide")

st.title("Poderes — restos a pagar por Poder")
st.warning(
    "**Leia antes de interpretar:** o RREO **não** publica a despesa total executada por Poder. "
    "Esta página mostra **restos a pagar** por Poder — obrigações de anos anteriores ainda **não "
    "quitadas** (Anexo 07 do RREO). É um indicador de contas atrasadas herdadas, **não** do gasto "
    "total de cada Poder no ano.",
    icon="⚠️",
)

anos = anos_disponiveis()
col_ano, col_bim = st.columns(2)
with col_ano:
    exercicio = st.selectbox("Exercício", options=anos, index=0)
ultimo_bimestre = bimestre_recente_uniao(exercicio)
with col_bim:
    bimestre = st.selectbox(
        "Bimestre (RREO)", options=list(range(1, ultimo_bimestre + 1)), index=ultimo_bimestre - 1
    )

tabela, entes_sem_dado = carregar_restos_poder(exercicio, bimestre)

if entes_sem_dado:
    st.warning("Restos a pagar não declarados para: " + ", ".join(entes_sem_dado) + f" no {bimestre}º bimestre de {exercicio}.", icon="⚠️")

if tabela.empty:
    st.error("Sem dados de restos a pagar por Poder para o período.")
    st.stop()

entes_disp = [n for n in ORDEM_ENTES if n in tabela["ente"].unique()]
entes_sel = st.multiselect("Entes", options=entes_disp, default=entes_disp)
tabela = tabela[tabela["ente"].isin(entes_sel)]
if tabela.empty:
    st.warning("Selecione ao menos um ente.")
    st.stop()

# ---------------------------------------------------------------------------
# Restos a pagar por Poder (barras agrupadas por ente)
# ---------------------------------------------------------------------------
st.header("Restos a pagar por Poder")
st.caption("Saldo total de restos a pagar (processados + não processados, exceto intra) de cada Poder.")

escala_entes = alt.Scale(domain=ORDEM_ENTES, range=list(CORES_POR_ENTE.values()))
poderes_presentes = [p for p in ORDEM_PODERES if p in tabela["poder"].unique()]
grafico = (
    alt.Chart(tabela)
    .mark_bar(cornerRadius=4)
    .encode(
        x=alt.X("poder:N", title="Poder", sort=poderes_presentes),
        y=alt.Y("restos_a_pagar:Q", title="Restos a pagar (R$)"),
        xOffset=alt.XOffset("ente:N", sort=entes_disp),
        color=alt.Color("ente:N", title="Ente", scale=escala_entes, sort=entes_disp),
        tooltip=[
            alt.Tooltip("ente:N", title="Ente"),
            alt.Tooltip("poder:N", title="Poder"),
            alt.Tooltip("restos_a_pagar:Q", title="Restos a pagar (R$)", format=",.2f"),
        ],
    )
    .properties(height=400)
)
st.altair_chart(grafico, width="stretch")

st.caption(
    "Observação: municípios possuem apenas Executivo e Legislativo (não têm Judiciário, "
    "Ministério Público ou Defensoria próprios), por isso esses Poderes aparecem só para União e estado."
)

# ---------------------------------------------------------------------------
# Tabela
# ---------------------------------------------------------------------------
st.header("Tabela")
tab = tabela.copy()
tab["restos_a_pagar"] = tab["restos_a_pagar"].map(formatar_reais)
tab = tab.rename(columns={"ente": "Ente", "nivel": "Nível", "poder": "Poder", "restos_a_pagar": "Restos a pagar (R$)"})
st.dataframe(tab[["Ente", "Nível", "Poder", "Restos a pagar (R$)"]], width="stretch", hide_index=True)
botao_download_csv(tab[["Ente", "Nível", "Poder", "Restos a pagar (R$)"]], f"restos_a_pagar_por_poder_{exercicio}_b{bimestre}.csv")
