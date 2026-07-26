"""Página: Tendências & Projeções — o estudo do comportamento do Estado.

Não é espelho de dados fechados: usa o histórico para **projetar** o fechamento do
ano corrente e ler o comportamento fiscal em contexto macro (Selic, inflação).
Toda projeção é rotulada como tal, com método explícito, faixa e erro histórico.
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
    carregar_receita,
    carregar_selic,
    fatores_ipca,
    formatar_reais,
    projecoes_fechamento,
    render_destaques,
    serie_anual_despesa,
    serie_peso_funcao,
)
from app.cores import CORES_POR_ENTE, ORDEM_ENTES
from analise.projecao import crescimento_vs_inflacao
from extract.inflacao import indice_ipca_anual
from extract.periodos import anos_disponiveis
from transform.fiscal import FUNCAO_ENCARGOS
from transform.receita import totais_receita_por_ente

st.set_page_config(page_title="Tendências & Projeções", page_icon="🛡️", layout="wide")

st.title("📈 Tendências & Projeções")
st.caption("O estudo do comportamento do Estado — do que já foi ao que vem por aí.")
abertura(
    "Aqui a gente **imagina o futuro com os dados de hoje**. A partir do histórico, projetamos como o "
    "ano corrente deve fechar, e lemos o comportamento fiscal ao lado da **Selic** e da **inflação**. "
    "Projeção **não é fato**: cada número futuro vem com o método, uma faixa e o erro histórico do método."
)

anos = anos_disponiveis()
ano_corrente = anos[0]
bim_atual = bimestre_recente_uniao(ano_corrente)
anos_hist = tuple(a for a in anos if a < ano_corrente)[:4]  # anos fechados recentes

# ---------------------------------------------------------------------------
# 1. Projeção do fechamento do ano corrente
# ---------------------------------------------------------------------------
st.header(f"Projeção de fechamento de {ano_corrente}")

if bim_atual >= 6 or not anos_hist:
    st.info(f"O exercício {ano_corrente} já está fechado (ou não há histórico) — sem necessidade de projeção.", icon="ℹ️")
    proj_por_ente = {}
else:
    st.caption(
        f"O RREO é acumulado: até o {bim_atual}º bimestre executa-se uma fração historicamente estável "
        f"do ano. **Projeção = realizado até agora ÷ essa fração.** A faixa vem do mínimo/máximo histórico."
    )
    proj_bruto = projecoes_fechamento(anos_hist, ano_corrente, bim_atual)
    proj_por_ente = {e: proj_bruto[e] for e in ORDEM_ENTES if e in proj_bruto}

    if proj_por_ente:
        for ente, p in proj_por_ente.items():
            conf = "🟢 alta" if (p["erro"] or 1) < 0.05 else ("🟡 média" if (p["erro"] or 1) < 0.12 else "🔴 baixa")
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.metric(f"🔮 {ente} — projeção {ano_corrente}", formatar_reais(p["projecao"]))
            if p.get("minimo") and p.get("maximo"):
                c2.caption(f"Faixa: {formatar_reais(p['minimo'])} — {formatar_reais(p['maximo'])}")
            if p["erro"] is not None:
                c3.caption(f"Confiança {conf} · o método errou em média **{p['erro']:.0%}** nos anos anteriores")
        st.warning(
            "🔮 **PROJEÇÃO, não valor fechado.** Estima o fim do ano a partir do ritmo atual e da "
            "sazonalidade histórica. Municípios costumam ser muito previsíveis (erro ~2%); a União "
            "oscila mais (gastos irregulares, refinanciamento da dívida) — confira a confiança em cada card.",
            icon="⚠️",
        )

# ---------------------------------------------------------------------------
# Destaques do guardião (tendência)
# ---------------------------------------------------------------------------
achados_tend = []
for ente, p in proj_por_ente.items():
    ant = p.get("fechado_anterior")
    if ant and p.get("projecao"):
        var = p["projecao"] / ant - 1
        sev = "atencao" if abs(var) >= 0.10 else "info"
        achados_tend.append({
            "icone": "🔮",
            "titulo": f"Ritmo de {ente}",
            "texto": f"Se mantiver o ritmo, **{ente}** fecha {ano_corrente} em torno de "
                     f"**{formatar_reais(p['projecao'])}** — {'+' if var >= 0 else ''}{var:.0%} vs o último ano fechado (nominal).",
            "severidade": sev,
        })
render_destaques(achados_tend[:4], titulo="🛡️ O que a tendência sugere")

st.divider()

# ---------------------------------------------------------------------------
# 2. Contexto macro: Selic × IPCA × peso da dívida
# ---------------------------------------------------------------------------
st.header("Contexto macro: juros, inflação e o peso da dívida")
st.caption(
    "A **Selic** (juros básicos) encarece o serviço da dívida pública; a **inflação** corrói o valor "
    "do orçamento. Aqui elas aparecem ao lado do peso dos **Encargos Especiais** da União (juros e "
    "amortização) — quando os juros sobem, a conta da dívida tende a pesar mais."
)
selic = carregar_selic(min(anos), ano_corrente)
idx = indice_ipca_anual(ano_corrente)
ipca_pct = {a: (idx[a] / idx[a - 1] - 1) for a in idx if (a - 1) in idx}
peso_enc = serie_peso_funcao(tuple(anos), (FUNCAO_ENCARGOS,))
peso_enc_uniao = dict(zip(peso_enc[peso_enc["ente"] == "União"]["ano"], peso_enc[peso_enc["ente"] == "União"]["peso"]))

linhas_macro = []
for a in sorted(set(list(selic) + list(ipca_pct) + list(peso_enc_uniao))):
    if a in selic:
        linhas_macro.append({"ano": a, "indicador": "Selic (% a.a.)", "valor": selic[a] / 100})
    if a in ipca_pct:
        linhas_macro.append({"ano": a, "indicador": "IPCA (% no ano)", "valor": ipca_pct[a]})
    if a in peso_enc_uniao:
        linhas_macro.append({"ano": a, "indicador": "Encargos/dívida (% da despesa União)", "valor": peso_enc_uniao[a]})
df_macro = pd.DataFrame(linhas_macro)
if not df_macro.empty:
    graf_macro = (
        alt.Chart(df_macro)
        .mark_line(point=True)
        .encode(
            x=alt.X("ano:O", title="Ano"),
            y=alt.Y("valor:Q", title="%", axis=alt.Axis(format="%")),
            color=alt.Color("indicador:N", title=None,
                            scale=alt.Scale(range=["#d03b3b", "#eda100", "#4a3aa7"])),
            tooltip=[alt.Tooltip("ano:O"), alt.Tooltip("indicador:N"), alt.Tooltip("valor:Q", format=".1%")],
        )
        .properties(height=360)
    )
    st.altair_chart(graf_macro, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# 3. O orçamento seguiu alguma regra? (crescimento real do gasto)
# ---------------------------------------------------------------------------
st.header("O gasto cresceu acima ou abaixo da inflação?")
st.caption(
    "Crescimento **real** (já descontada a inflação) da despesa realizada, ano a ano. Acima de zero = "
    "o governo passou a gastar mais em termos reais; abaixo = encolheu. Entre 2017 e 2023 vigorou o "
    "**teto de gastos** federal (EC 95), que limitava o crescimento à inflação do ano anterior."
)
ente_regra = st.selectbox("Ente", options=ORDEM_ENTES, index=0, key="ente_regra")
serie_d = serie_anual_despesa(tuple(anos))
serie_ente_d = dict(zip(
    serie_d[(serie_d["ente"] == ente_regra) & (~serie_d["parcial"])]["ano"],
    serie_d[(serie_d["ente"] == ente_regra) & (~serie_d["parcial"])]["realizado"],
))
fatores = fatores_ipca(ano_corrente)
cresc = crescimento_vs_inflacao(serie_ente_d, fatores)
if cresc:
    df_cresc = pd.DataFrame(cresc)
    graf_cresc = (
        alt.Chart(df_cresc)
        .mark_bar(cornerRadius=3)
        .encode(
            x=alt.X("ano:O", title="Ano"),
            y=alt.Y("real:Q", title="Crescimento real da despesa", axis=alt.Axis(format="%")),
            color=alt.condition(alt.datum.real >= 0, alt.value("#1baf7a"), alt.value("#d03b3b")),
            tooltip=[alt.Tooltip("ano:O"), alt.Tooltip("real:Q", title="Real", format="+.1%"),
                     alt.Tooltip("nominal:Q", title="Nominal", format="+.1%")],
        )
        .properties(height=320)
    )
    st.altair_chart(graf_cresc, width="stretch")
    if ente_regra == "União":
        st.caption("⚠️ Na União, oscilações fortes refletem também o refinanciamento da dívida embutido em Encargos Especiais — leia com cautela.")
else:
    st.info("Sem série suficiente para este ente.", icon="ℹ️")

st.divider()

# ---------------------------------------------------------------------------
# 4. De onde vem o dinheiro (composição + crescimento da arrecadação)
# ---------------------------------------------------------------------------
st.header("De onde vem o dinheiro?")
st.caption("Composição da receita realizada do ano corrente e o quanto a arrecadação própria cresceu além da inflação.")
rec_atual, _ = carregar_receita(ano_corrente, bim_atual)
if not rec_atual.empty:
    comp = rec_atual[rec_atual["ente"] == ente_regra].groupby("categoria")["realizada"].sum().sort_values(ascending=False).head(8).reset_index()
    if not comp.empty:
        graf_comp = (
            alt.Chart(comp)
            .mark_bar(cornerRadius=3)
            .encode(
                x=alt.X("realizada:Q", title="R$ arrecadado no ano"),
                y=alt.Y("categoria:N", title=None, sort="-x"),
                color=alt.value(CORES_POR_ENTE.get(ente_regra, "#2a78d6")),
                tooltip=[alt.Tooltip("categoria:N"), alt.Tooltip("realizada:Q", title="R$", format=",.0f")],
            )
            .properties(height=max(220, 34 * len(comp)))
        )
        st.altair_chart(graf_comp, width="stretch")
        st.caption(f"Composição da receita de **{ente_regra}** em {ano_corrente} (até o {bim_atual}º bimestre).")

# ---------------------------------------------------------------------------
# Nota honesta: dívida ativa
# ---------------------------------------------------------------------------
with st.expander("📌 E os impostos que não estão sendo pagos? (limitação de fonte)"):
    st.markdown(
        """
O **estoque de dívida ativa** — impostos lançados mas não pagos, que o poder público ainda tem a
receber — **não está no RREO** (a fonte deste painel). Ele fica no **Balanço Patrimonial** e na
**Declaração de Contas Anuais (DCA)** do SICONFI, com periodicidade anual e estrutura diferente.

Fica registrado como evolução futura: integrar a DCA permitiria mostrar quanto cada ente tem a
receber de tributos inadimplidos — um indicador poderoso de eficiência da arrecadação.
        """.strip()
    )
