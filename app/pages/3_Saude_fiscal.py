"""Página: Saúde fiscal — "o governo está apertado?".

Três sinais de aperto, uniformes entre os entes e baseados em dados que já temos:
- Resultado orçamentário no período (receita − despesa).
- Peso da Previdência Social na despesa (fatia crescente = pressão estrutural).
- Peso dos Encargos Especiais (juros/amortização da dívida e sentenças judiciais).

Precatórios não têm API pública consolidada; ver nota ao final.
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
    formatar_pct,
    formatar_reais,
    serie_peso_funcao,
)
from app.cores import CORES_POR_ENTE, ORDEM_ENTES
from extract.periodos import anos_disponiveis
from transform.fiscal import (
    FUNCAO_ENCARGOS,
    FUNCAO_PREVIDENCIA,
    classificar_saldo,
    peso_por_funcao,
    resultado_orcamentario,
)
from transform.receita import totais_receita_por_ente

st.set_page_config(page_title="Saúde fiscal", layout="wide")

st.title("Saúde fiscal — o governo está apertado?")
st.caption(
    "Sinais de aperto de contas, comparáveis entre os três níveis da federação. "
    "Fonte: RREO Anexos 01 (receita) e 02 (despesa por função) do SICONFI."
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

tabela_despesa, entes_sem_dado, _ = carregar_dados(exercicio, bimestre)
tabela_receita, _ = carregar_receita(exercicio, bimestre)

if tabela_despesa.empty:
    st.error("Sem dados de despesa para o período.")
    st.stop()

# ---------------------------------------------------------------------------
# 1. Resultado orçamentário (receita − despesa)
# ---------------------------------------------------------------------------
st.header("Resultado orçamentário no período")
st.caption("Receita realizada menos despesa liquidada (ambas exceto intra). Déficit = aperto de caixa.")

receita_tot = totais_receita_por_ente(tabela_receita).set_index("ente")["realizada"] if not tabela_receita.empty else pd.Series(dtype=float)
despesa_tot = tabela_despesa.groupby("ente")["realizado"].sum()
resultado = resultado_orcamentario(receita_tot, despesa_tot)

if resultado.empty:
    st.info("Sem receita declarada neste período para calcular o resultado.", icon="ℹ️")
else:
    resultado = resultado.set_index("ente")
    entes_ord = [e for e in ORDEM_ENTES if e in resultado.index]
    cards = st.columns(len(entes_ord))
    for coluna, ente in zip(cards, entes_ord):
        saldo = resultado.loc[ente, "saldo"]
        status = classificar_saldo(saldo)
        with coluna:
            st.metric(label=ente, value=formatar_reais(saldo))
            st.caption(f"{status['icone']} {status['rotulo']} orçamentário")

# ---------------------------------------------------------------------------
# 2. Peso da Previdência e dos Encargos Especiais (snapshot do período)
# ---------------------------------------------------------------------------
st.header("Peso da Previdência e dos Encargos Especiais")
st.caption(
    "Fatia da despesa comprometida com Previdência Social e com Encargos Especiais "
    "(juros/amortização da dívida e sentenças judiciais). Fatias altas/crescentes = rigidez."
)

prev = peso_por_funcao(tabela_despesa, FUNCAO_PREVIDENCIA).set_index("ente")
enc = peso_por_funcao(tabela_despesa, FUNCAO_ENCARGOS).set_index("ente")
entes_ord = [e for e in ORDEM_ENTES if e in prev.index]

colp, cole = st.columns(2)
with colp:
    st.subheader("🏛️ Previdência Social")
    for ente in entes_ord:
        st.metric(label=ente, value=formatar_pct(prev.loc[ente, "peso"]))
with cole:
    st.subheader("💸 Encargos Especiais")
    for ente in entes_ord:
        st.metric(label=ente, value=formatar_pct(enc.loc[ente, "peso"]))

# ---------------------------------------------------------------------------
# 3. Evolução histórica do peso (tendência)
# ---------------------------------------------------------------------------
st.header("Evolução do peso ao longo dos anos")
st.caption("Uma fatia que sobe ano após ano indica pressão fiscal estrutural crescente.")

funcao_escolhida = st.radio(
    "Função", [FUNCAO_PREVIDENCIA, FUNCAO_ENCARGOS], horizontal=True
)
serie = serie_peso_funcao(tuple(anos), (FUNCAO_PREVIDENCIA, FUNCAO_ENCARGOS))
serie_f = serie[serie["funcao"] == funcao_escolhida]

if serie_f.empty:
    st.info("Sem série histórica disponível para esta função.", icon="ℹ️")
else:
    escala = alt.Scale(domain=ORDEM_ENTES, range=list(CORES_POR_ENTE.values()))
    grafico = (
        alt.Chart(serie_f)
        .mark_line(point=True)
        .encode(
            x=alt.X("ano:O", title="Ano"),
            y=alt.Y("peso:Q", title="% da despesa", axis=alt.Axis(format="%")),
            color=alt.Color("ente:N", title="Ente", scale=escala, sort=ORDEM_ENTES),
            tooltip=[
                alt.Tooltip("ente:N", title="Ente"),
                alt.Tooltip("ano:O", title="Ano"),
                alt.Tooltip("peso:Q", title="% da despesa", format=".1%"),
                alt.Tooltip("realizado:Q", title="Valor (R$)", format=",.2f"),
                alt.Tooltip("parcial:N", title="Ano parcial?"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(grafico, width="stretch")

# ---------------------------------------------------------------------------
# Nota sobre precatórios
# ---------------------------------------------------------------------------
with st.expander("📌 Sobre precatórios (limitação de fonte)"):
    st.markdown(
        """
Os **precatórios** (dívidas judiciais que o poder público é obrigado a pagar) **não têm
uma API pública consolidada** por ente. O CNJ mantém apenas um painel visual, sem dados
abertos padronizados, e o SICONFI não os isola em um demonstrativo próprio.

No RREO, os precatórios aparecem **diluídos** dentro da função **"Encargos Especiais"**
(e na subfunção "Sentenças Judiciais"). Por isso usamos Encargos Especiais como *proxy*
de rigidez/obrigações judiciais — **não** como o estoque exato de precatórios.

Extrair o valor específico de precatórios exigiria: (a) descer ao nível de **subfunção**
no Anexo 02 (hoje filtramos só as 28 funções), ou (b) integrar uma fonte externa
(ex.: portais de precatórios dos tribunais). Fica registrado como evolução futura.
        """.strip()
    )
