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
    abertura,
    bimestre_recente_uniao,
    carregar_dados,
    carregar_receita,
    fatores_ipca,
    formatar_pct,
    formatar_reais,
    populacoes_por_ente,
    serie_anual_despesa,
    serie_anual_receita,
    serie_peso_funcao,
)
from app.cores import CORES_POR_ENTE, ORDEM_ENTES
from analise.insights import per_capita, populacoes_validas
from extract.inflacao import deflacionar
from extract.periodos import anos_disponiveis
from transform.fiscal import (
    FUNCAO_ENCARGOS,
    FUNCAO_PREVIDENCIA,
    classificar_saldo,
    peso_por_funcao,
    resultado_orcamentario,
)
from transform.receita import totais_receita_por_ente

st.set_page_config(page_title="Saúde fiscal", page_icon="🛡️", layout="wide")

st.title("Saúde fiscal — o governo está apertado?")
st.caption(
    "Sinais de aperto de contas, comparáveis entre os três níveis da federação. "
    "Fonte: RREO Anexos 01 (receita) e 02 (despesa por função) do SICONFI."
)
abertura(
    "Um governo apertado gasta cada vez mais com o **passado** (previdência, dívida) e menos com o "
    "**presente** (serviços). Aqui você vê esses sinais, quanto vai para **saúde e educação por "
    "habitante**, e se receita cobre despesa ao longo dos anos."
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
# 2b. Saúde e Educação por habitante (o que chega ao cidadão)
# ---------------------------------------------------------------------------
st.header("Saúde e Educação por habitante")
st.caption(
    "Quanto cada governo gasta por pessoa nas duas áreas que mais afetam a vida do cidadão. "
    "A União fica de fora (população federal incorreta na fonte)."
)
_pops = populacoes_validas(populacoes_por_ente(exercicio, bimestre))
if _pops:
    saude = tabela_despesa[tabela_despesa["funcao"] == "Saúde"].groupby("ente")["realizado"].sum().to_dict()
    educ = tabela_despesa[tabela_despesa["funcao"] == "Educação"].groupby("ente")["realizado"].sum().to_dict()
    pc_saude = per_capita(saude, _pops)
    pc_educ = per_capita(educ, _pops)
    linhas_se = []
    for ente in _pops:
        if ente in pc_saude:
            linhas_se.append({"ente": ente, "área": "Saúde", "por_habitante": pc_saude[ente]})
        if ente in pc_educ:
            linhas_se.append({"ente": ente, "área": "Educação", "por_habitante": pc_educ[ente]})
    df_se = pd.DataFrame(linhas_se)
    if not df_se.empty:
        graf_se = (
            alt.Chart(df_se)
            .mark_bar(cornerRadius=3)
            .encode(
                x=alt.X("por_habitante:Q", title="R$ por habitante"),
                y=alt.Y("ente:N", title=None, sort="-x"),
                yOffset=alt.YOffset("área:N"),
                color=alt.Color("área:N", title=None, scale=alt.Scale(domain=["Saúde", "Educação"], range=["#1baf7a", "#2a78d6"])),
                tooltip=[alt.Tooltip("ente:N"), alt.Tooltip("área:N"), alt.Tooltip("por_habitante:Q", title="R$/hab", format=",.0f")],
            )
            .properties(height=max(220, 46 * len(_pops)))
        )
        st.altair_chart(graf_se, width="stretch")
    st.caption(
        "📏 **Contexto legal:** a Constituição exige aplicar no mínimo **15% em saúde** (EC 29/2000) e "
        "**25% em educação** (Art. 212) — mas sobre a *receita de impostos*, não sobre a despesa total. "
        "Os valores acima são gasto por habitante, uma leitura complementar (não o cálculo do mínimo)."
    )
else:
    st.info("Sem população disponível para o per capita neste período.", icon="ℹ️")

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
# 4. Resultado orçamentário ao longo do tempo (receita − despesa, real)
# ---------------------------------------------------------------------------
st.header("Resultado orçamentário ao longo dos anos")
st.caption(
    "Trajetória de receita, despesa e saldo por ano. Anos fechados usam o 6º bimestre; "
    "o ano corrente é parcial."
)
st.caption(
    "⚠️ **Leitura importante:** a receita aqui inclui **operações de crédito** (empréstimos), "
    "então o resultado *orçamentário* tende a ser positivo mesmo com aperto real. O indicador de "
    "aperto de fato é o resultado **primário** (que exclui financiamento) — não isolado nesta visão."
)

ano_base_hist = anos[0]
correcao_hist = st.radio(
    "Valores",
    ["Nominais", f"Reais (IPCA, R$ de {ano_base_hist})"],
    horizontal=True,
    key="correcao_hist",
)
usar_real_hist = correcao_hist.startswith("Reais")

ente_hist = st.selectbox("Ente", options=ORDEM_ENTES, index=0, key="ente_hist")
serie_d = serie_anual_despesa(tuple(anos))
serie_r = serie_anual_receita(tuple(anos))
sd = serie_d[serie_d["ente"] == ente_hist][["ano", "realizado", "parcial"]].rename(columns={"realizado": "Despesa"})
sr = serie_r[serie_r["ente"] == ente_hist][["ano", "realizada"]].rename(columns={"realizada": "Receita"})
hist = sd.merge(sr, on="ano", how="inner").sort_values("ano")

if hist.empty:
    st.info("Sem série de receita e despesa combinada para este ente.", icon="ℹ️")
else:
    if usar_real_hist:
        fatores_h = fatores_ipca(ano_base_hist)
        for col in ["Despesa", "Receita"]:
            hist[col] = hist.apply(lambda r: deflacionar(r[col], int(r["ano"]), fatores_h), axis=1)
    hist["Saldo"] = hist["Receita"] - hist["Despesa"]

    barras = hist.melt(id_vars=["ano"], value_vars=["Receita", "Despesa"], var_name="tipo", value_name="valor")
    grafico_rd_hist = (
        alt.Chart(barras)
        .mark_bar()
        .encode(
            x=alt.X("ano:O", title="Ano"),
            y=alt.Y("valor:Q", title="R$"),
            xOffset=alt.XOffset("tipo:N", sort=["Receita", "Despesa"]),
            color=alt.Color("tipo:N", title=None,
                            scale=alt.Scale(domain=["Receita", "Despesa"], range=[CORES_POR_ENTE[ORDEM_ENTES[1]], CORES_POR_ENTE[ORDEM_ENTES[0]]])),
            tooltip=[alt.Tooltip("ano:O"), alt.Tooltip("tipo:N"), alt.Tooltip("valor:Q", title="R$", format=",.2f")],
        )
        .properties(height=340)
    )
    linha_saldo = (
        alt.Chart(hist)
        .mark_line(point=True, color="#333", strokeDash=[4, 3])
        .encode(
            x=alt.X("ano:O"),
            y=alt.Y("Saldo:Q"),
            tooltip=[alt.Tooltip("ano:O"), alt.Tooltip("Saldo:Q", title="Saldo (R$)", format=",.2f")],
        )
    )
    st.altair_chart(grafico_rd_hist, width="stretch")
    st.caption("Linha tracejada = saldo (receita − despesa). No gráfico acima, barras de Receita vs Despesa.")
    st.altair_chart(linha_saldo.properties(height=220), width="stretch")

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
