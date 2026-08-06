"""Página: Estudos Econométricos — relatório técnico.

Formato deliberadamente denso: hipótese → método → fórmula → resultado → veredito →
interpretação → limitações → referência. Sem cards decorativos. O objetivo é
**conteúdo analítico**, não apresentação.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from app.comum import botao_download_csv, negrito_para_html, series_para_estudos
from analise.estudos import (
    estudo_ciclo_politico,
    estudo_concentracao_receita,
    estudo_desigualdade_per_capita,
    estudo_passthrough_juros,
    estudo_rigidez,
    estudo_sustentabilidade,
)
from extract.periodos import anos_disponiveis

st.set_page_config(page_title="Estudos econométricos", page_icon="🛡️", layout="wide")

CORES_SEVERIDADE = {"alerta": "#d03b3b", "atencao": "#fab219", "positivo": "#0ca30c", "info": "#2a78d6"}

st.title("🔬 Estudos econométricos")
st.caption(
    "Análise fiscal com método declarado, teste estatístico e limitações explícitas — "
    "não apenas descrição dos dados."
)

anos = anos_disponiveis()
ano_corrente = anos[0]
col_a, col_b = st.columns([1, 3])
with col_a:
    ano_ref = st.selectbox(
        "Ano de referência (estudos de corte transversal)",
        options=[a for a in anos if a <= ano_corrente], index=1 if len(anos) > 1 else 0,
        help="Estudos 3, 4 e 5 são de um ano; 1, 2 e 6 usam toda a série.",
    )

# ---------------------------------------------------------------------------
# Nota metodológica geral
# ---------------------------------------------------------------------------
with st.expander("📐 Nota metodológica — leia antes dos resultados", expanded=True):
    st.markdown(
        f"""
**Amostra.** 7 entes federativos (União, Estado de São Paulo e 5 municípios paulistas),
exercícios de {min(anos)} a {ano_corrente}. A seleção é **por conveniência**, não aleatória.

**Natureza dos resultados.** São **exploratórios e descritivos da amostra** — não constituem
inferência sobre a população de entes brasileiros, nem estimativas causais. Onde há teste de
hipótese, o desenho é observacional: mede-se **associação**, não efeito causal.

**Fontes.** Execução orçamentária: SICONFI/Tesouro Nacional (RREO, Anexos 01 e 02, dado do 6º
bimestre = ano fechado). Juros: Banco Central (SGS, série 432). Deflator: IPCA/IBGE.

**Deflação.** Séries reais usam o IPCA com base no ano mais recente. Valores nominais são
indicados como tal.

**Significância.** Onde aplicável, o p-valor vem de **teste de permutação** (10.000 reamostragens,
semente fixa = 42, portanto reprodutível), que não pressupõe normalidade — adequado a amostras
pequenas. Para o coeficiente de regressão usa-se a regra prática |t| > 2 ≈ significativo a ~5%.

**Ausências declaradas.** Elasticidade-PIB e teste da Lei de Wagner **não** foram feitos: a API do
IBGE/SIDRA passou a bloquear as requisições deste projeto, e o PIB municipal ficou indisponível.
Testes formais de cointegração (Engle-Granger, Johansen) exigiriam séries longas — com ~10
observações anuais seriam cientificismo vazio, e por isso não foram aplicados.
        """.strip()
    )


def render_estudo(estudo: dict) -> None:
    """Renderiza um estudo no formato de relatório."""
    cor = CORES_SEVERIDADE.get(estudo.get("severidade", "info"), CORES_SEVERIDADE["info"])
    st.markdown("---")
    st.subheader(estudo["titulo"])

    st.markdown("**Hipótese**")
    st.markdown(estudo["hipotese"])

    st.markdown("**Método**")
    st.markdown(estudo["metodo"])
    if estudo.get("formula_latex"):
        st.latex(estudo["formula_latex"])

    estat = estudo.get("estatisticas")
    if isinstance(estat, pd.DataFrame) and not estat.empty:
        st.markdown("**Resultado**")
        st.dataframe(estat, width="stretch", hide_index=True)

    # Veredito destacado pela severidade — o único elemento visual, porque é a conclusão.
    st.markdown(
        f"<div style='border-left:6px solid {cor};background:rgba(128,128,128,0.08);"
        f"padding:10px 16px;border-radius:6px;margin:8px 0'>"
        f"<b>Veredito.</b> {negrito_para_html(estudo['veredito'])}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(f"**Interpretação.** {estudo['interpretacao']}")

    with st.expander("⚠️ Limitações deste estudo"):
        for r in estudo["ressalvas"]:
            st.markdown(f"- {r}")
    st.caption(f"📚 Referência: {estudo['referencia']}")


# ---------------------------------------------------------------------------
# Carga única dos dados
# ---------------------------------------------------------------------------
dados = series_para_estudos(tuple(a for a in anos if a <= ano_corrente), ano_ref)

if not dados["despesa_por_ente"]:
    st.error("Não foi possível montar as séries para os estudos.")
    st.stop()

estudos = [
    estudo_sustentabilidade(dados["despesa_por_ente"], dados["receita_por_ente"]),
    estudo_ciclo_politico(dados["crescimento_real_por_ente"], dados["niveis"]),
    estudo_rigidez(dados["despesa_ref"]),
    estudo_concentracao_receita(dados["receita_ref"]),
    estudo_desigualdade_per_capita(dados["despesa_por_ente"], dados["populacoes"], ano_ref),
    estudo_passthrough_juros(dados["selic"], dados["peso_encargos_uniao"]),
]

# Sumário executivo dos vereditos (denso, uma linha por estudo).
st.markdown("### Sumário dos achados")
st.dataframe(
    pd.DataFrame([
        {"Estudo": e["titulo"].split("—")[0].strip(), "Veredito": e["veredito"].replace("**", "")}
        for e in estudos
    ]),
    width="stretch", hide_index=True,
)

for e in estudos:
    render_estudo(e)

# ---------------------------------------------------------------------------
# Reprodutibilidade
# ---------------------------------------------------------------------------
st.markdown("---")
with st.expander("🔁 Reprodutibilidade e download"):
    st.markdown(
        "Todas as estatísticas são calculadas em `analise/econometria.py` (primitivas com a fórmula "
        "na docstring) e `analise/estudos.py` (aplicação aos dados), com testes em "
        "`tests/test_econometria.py` validando cada primitiva contra resultado analítico conhecido "
        "(ex.: OLS sobre reta perfeita recupera β exato; Gini de distribuição igual = 0; HHI de "
        "monopólio = 1). O teste de permutação usa semente fixa, então o p-valor é idêntico a cada "
        "execução."
    )
    for e in estudos:
        est = e.get("estatisticas")
        if isinstance(est, pd.DataFrame) and not est.empty:
            botao_download_csv(est, f"{e['titulo'].split('.')[0].strip()}_{ano_ref}.csv",
                               label=f"⬇️ {e['titulo'].split('—')[0].strip()}")
