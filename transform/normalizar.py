"""Normaliza o RREO bruto (formato longo da API) numa tabela única e comparável
entre União, estado e municípios: ente, nivel, funcao, previsao_inicial,
previsao_atualizada, realizado.
"""

import pandas as pd

from extract.config import (
    COLUNA_PREVISAO_INICIAL,
    COLUNA_PREVISAO_ATUALIZADA,
    COLUNA_REALIZADO,
)
from transform.config import FUNCOES_GOVERNO, ROTULO_DESPESA_LIQUIDA

COLUNAS_RELEVANTES = {
    COLUNA_PREVISAO_INICIAL: "previsao_inicial",
    COLUNA_PREVISAO_ATUALIZADA: "previsao_atualizada",
    COLUNA_REALIZADO: "realizado",
}

COLUNAS_SAIDA = ["ente", "nivel", "funcao", "previsao_inicial", "previsao_atualizada", "realizado"]


def normalizar_rreo(df_bruto: pd.DataFrame, nome_ente: str, nivel: str) -> pd.DataFrame:
    """Converte o RREO bruto de um ente (formato longo) numa linha por função de governo."""
    if df_bruto.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df = df_bruto[
        (df_bruto["rotulo"] == ROTULO_DESPESA_LIQUIDA)
        & (df_bruto["conta"].isin(FUNCOES_GOVERNO))
        & (df_bruto["coluna"].isin(COLUNAS_RELEVANTES))
    ].copy()

    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df["campo"] = df["coluna"].map(COLUNAS_RELEVANTES)

    tabela = (
        df.pivot_table(index="conta", columns="campo", values="valor", aggfunc="sum")
        .reset_index()
        .rename(columns={"conta": "funcao"})
    )

    for campo in COLUNAS_RELEVANTES.values():
        if campo not in tabela.columns:
            tabela[campo] = pd.NA

    tabela.insert(0, "nivel", nivel)
    tabela.insert(0, "ente", nome_ente)

    return tabela[COLUNAS_SAIDA]


def normalizar_varios(dados_por_ente: dict) -> pd.DataFrame:
    """dados_por_ente: {chave: {"df": DataFrame bruto, "nome": str, "nivel": str}}."""
    tabelas = [
        normalizar_rreo(info["df"], info["nome"], info["nivel"])
        for info in dados_por_ente.values()
    ]
    tabelas = [t for t in tabelas if not t.empty]

    if not tabelas:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    return pd.concat(tabelas, ignore_index=True)
