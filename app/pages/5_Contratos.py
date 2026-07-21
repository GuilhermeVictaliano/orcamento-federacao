"""Página: Contratos (PNCP) — para auditoria pelos usuários.

Expõe os contratos publicados por um órgão no Portal Nacional de Contratações
Públicas (PNCP), ordenados por valor, para que a pessoa inspecione objeto,
fornecedor e valor — e abra o registro oficial. Não há juízo automático de
"superfaturamento": quem audita é o usuário.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from app.comum import botao_download_csv, carregar_contratos, fatores_ipca, formatar_reais
from extract.inflacao import deflacionar
from extract.periodos import anos_disponiveis
from extract.pncp import ORGAOS_CONHECIDOS
from transform.contratos import resumo_contratos

st.set_page_config(page_title="Contratos (PNCP)", layout="wide")

st.title("Contratos públicos — auditoria pelo cidadão (PNCP)")
st.info(
    "Contratos publicados no **PNCP** (Portal Nacional de Contratações Públicas). "
    "Aqui você **inspeciona** os contratos de um órgão — ordene por valor, leia o objeto, "
    "veja o fornecedor e abra o registro oficial. Nenhum contrato é classificado "
    "automaticamente como irregular: a auditoria é sua.",
    icon="🔍",
)
st.warning(
    "**Cobertura parcial, por órgão.** O PNCP só permite consulta por **CNPJ de órgão** — "
    "um ente grande tem muitos órgãos (cada um com seu CNPJ) e a adesão ao PNCP é parcial e "
    "cresceu ao longo do tempo. Portanto **esta lista não é o conjunto completo** de contratos "
    "do ente, e os contratos do PNCP **não trazem a função de governo**, então a ligação com a "
    "aba de despesas é aproximada (por órgão), não um vínculo exato contrato-a-função.",
    icon="⚠️",
)

col_org, col_ano = st.columns([2, 1])
with col_org:
    opcoes = list(ORGAOS_CONHECIDOS.keys()) + ["Outro CNPJ (digitar)"]
    escolha = st.selectbox("Órgão", options=opcoes, index=0)
with col_ano:
    ano = st.selectbox("Ano", options=[a for a in anos_disponiveis() if a <= 2026], index=0)

if escolha == "Outro CNPJ (digitar)":
    cnpj_raw = st.text_input("CNPJ do órgão (só números)", placeholder="ex.: 46395000000139")
    cnpj = "".join(ch for ch in cnpj_raw if ch.isdigit())
    if not cnpj:
        st.info("Digite um CNPJ de órgão para consultar. Dica: o CNPJ aparece no registro do contrato no PNCP.", icon="ℹ️")
        st.stop()
else:
    cnpj = ORGAOS_CONHECIDOS[escolha]

tabela, erro = carregar_contratos(cnpj, ano)

if erro:
    st.error(erro + " Tente novamente em instantes.")
    st.stop()

if tabela.empty:
    st.warning(f"Nenhum contrato encontrado para o CNPJ {cnpj} em {ano} (pode ser adesão parcial ao PNCP).", icon="⚠️")
    st.stop()

ano_base = anos_disponiveis()[0]
if ano < ano_base and st.checkbox(
    f"Corrigir valores por IPCA (mostrar em reais de {ano_base})",
    help="Deflaciona os valores do contrato para reais de hoje — útil para comparar contratos de anos diferentes.",
):
    fatores = fatores_ipca(ano_base)
    for col in ["valor_global", "valor_inicial"]:
        tabela[col] = tabela[col].map(lambda v: deflacionar(v, ano, fatores))
    st.caption(f"💡 Valores corrigidos pelo IPCA para reais de {ano_base}.")

# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------
resumo = resumo_contratos(tabela)
c1, c2, c3 = st.columns(3)
c1.metric("Contratos encontrados", f"{resumo['quantidade']:,}".replace(",", "."))
c2.metric("Valor total (global)", formatar_reais(resumo["valor_total"]))
c3.metric("Maior contrato", formatar_reais(resumo["maior"]))

# ---------------------------------------------------------------------------
# Filtros de auditoria
# ---------------------------------------------------------------------------
st.header("Contratos (ordenados por valor)")
col_busca, col_min = st.columns([2, 1])
with col_busca:
    termo = st.text_input("Buscar no objeto ou fornecedor", placeholder="ex.: informática, obras, locação")
with col_min:
    valor_min = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=100_000.0, format="%.2f")

filtrada = tabela.copy()
if termo:
    mask = (
        filtrada["objeto"].str.contains(termo, case=False, na=False)
        | filtrada["fornecedor"].str.contains(termo, case=False, na=False)
    )
    filtrada = filtrada[mask]
if valor_min > 0:
    filtrada = filtrada[filtrada["valor_global"].fillna(0) >= valor_min]

if filtrada.empty:
    st.warning("Nenhum contrato corresponde aos filtros.")
    st.stop()

exib = filtrada.copy()
exib["Valor global"] = exib["valor_global"].map(formatar_reais)
exib["Valor inicial"] = exib["valor_inicial"].map(formatar_reais)
exib = exib.rename(
    columns={
        "objeto": "Objeto", "fornecedor": "Fornecedor", "ni_fornecedor": "CNPJ/CPF fornecedor",
        "data_assinatura": "Assinatura", "vigencia_inicio": "Vigência início",
        "vigencia_fim": "Vigência fim", "orgao": "Órgão", "unidade": "Unidade", "link": "Ver no PNCP",
    }
)
st.dataframe(
    exib[[
        "Objeto", "Fornecedor", "CNPJ/CPF fornecedor", "Valor global", "Valor inicial",
        "Assinatura", "Vigência início", "Vigência fim", "Unidade", "Ver no PNCP",
    ]],
    width="stretch",
    hide_index=True,
    column_config={
        "Ver no PNCP": st.column_config.LinkColumn("Ver no PNCP", display_text="abrir"),
        "Objeto": st.column_config.TextColumn("Objeto", width="large"),
    },
)
botao_download_csv(filtrada, f"contratos_{cnpj}_{ano}.csv")
st.caption(
    "Dica de auditoria: ordene por valor, compare o objeto com o preço, procure fornecedores "
    "recorrentes e abra o registro oficial no PNCP para ver empenhos, aditivos e documentos."
)
