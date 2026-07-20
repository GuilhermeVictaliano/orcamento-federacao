"""Normaliza o RREO-Anexo 01 (Balanço Orçamentário), lado da RECEITA, numa tabela
comparável entre entes: uma linha por categoria econômica de receita, com previsão
e valor realizado (arrecadado) acumulado até o bimestre.

Usamos o `cod_conta` (identificador estável, sem acento) em vez do texto de `conta`
para filtrar as linhas — o texto vem com acentuação inconsistente da API.

Convenção "exceto intra-orçamentárias": igual à despesa, ignoramos receitas
intra-orçamentárias (transferências dentro do próprio ente) para não inflar o total.
As categorias abaixo somam exatamente `ReceitasExcetoIntraOrcamentarias`.
"""

import pandas as pd

from extract.config import (
    COLUNA_RECEITA_PREVISAO_INICIAL,
    COLUNA_RECEITA_PREVISAO_ATUALIZADA,
    COLUNA_RECEITA_REALIZADA,
)

COLUNAS_RELEVANTES = {
    COLUNA_RECEITA_PREVISAO_INICIAL: "previsao_inicial",
    COLUNA_RECEITA_PREVISAO_ATUALIZADA: "previsao_atualizada",
    COLUNA_RECEITA_REALIZADA: "realizada",
}

# cod_conta -> rótulo amigável. São as categorias econômicas que compõem a receita
# "exceto intra": as correntes e as de capital. A soma delas = total exceto intra.
CATEGORIAS_RECEITA = {
    # Correntes
    "ReceitaTributaria": "Tributária (impostos, taxas)",
    "ReceitaDeContribuicoes": "Contribuições",
    "ReceitaPatrimonial": "Patrimonial",
    "ReceitaAgropecuaria": "Agropecuária",
    "ReceitaIndustrial": "Industrial",
    "ReceitaDeServicos": "Serviços",
    "TransferenciasCorrentes": "Transferências correntes",
    "OutrasReceitasCorrentes": "Outras correntes",
    "ReceitasCorrentesAClassificar": "Correntes a classificar",
    # Capital
    "ReceitasDeOperacoesDeCredito": "Operações de crédito",
    "AlienacaoDeBens": "Alienação de bens",
    "AmortizacoesDeEmprestimos": "Amortizações de empréstimos",
    "TransferenciasDeCapital": "Transferências de capital",
    "OutrasReceitasDeCapital": "Outras de capital",
}

COD_TOTAL_EXCETO_INTRA = "ReceitasExcetoIntraOrcamentarias"

COLUNAS_SAIDA = ["ente", "nivel", "categoria", "previsao_inicial", "previsao_atualizada", "realizada"]


def normalizar_receita(df_bruto: pd.DataFrame, nome_ente: str, nivel: str) -> pd.DataFrame:
    """Converte o Anexo 01 bruto de um ente numa linha por categoria de receita."""
    if df_bruto.empty or "cod_conta" not in df_bruto.columns:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df = df_bruto[
        df_bruto["cod_conta"].isin(CATEGORIAS_RECEITA)
        & df_bruto["coluna"].isin(COLUNAS_RELEVANTES)
    ].copy()

    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df["campo"] = df["coluna"].map(COLUNAS_RELEVANTES)
    df["categoria"] = df["cod_conta"].map(CATEGORIAS_RECEITA)

    tabela = (
        df.pivot_table(index="categoria", columns="campo", values="valor", aggfunc="sum")
        .reset_index()
    )

    for campo in COLUNAS_RELEVANTES.values():
        if campo not in tabela.columns:
            tabela[campo] = pd.NA

    tabela.insert(0, "nivel", nivel)
    tabela.insert(0, "ente", nome_ente)

    return tabela[COLUNAS_SAIDA]


def normalizar_receita_varios(dados_por_ente: dict) -> pd.DataFrame:
    """dados_por_ente: {chave: {"df": DataFrame bruto do Anexo 01, "nome": str, "nivel": str}}."""
    tabelas = [
        normalizar_receita(info["df"], info["nome"], info["nivel"])
        for info in dados_por_ente.values()
    ]
    tabelas = [t for t in tabelas if not t.empty]

    if not tabelas:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    return pd.concat(tabelas, ignore_index=True)


def totais_receita_por_ente(tabela_receita: pd.DataFrame) -> pd.DataFrame:
    """Agrega a receita por ente (soma das categorias = total exceto intra)."""
    if tabela_receita.empty:
        return pd.DataFrame(columns=["ente", "nivel", "previsao_inicial", "previsao_atualizada", "realizada"])
    return (
        tabela_receita.groupby(["ente", "nivel"], as_index=False)[
            ["previsao_inicial", "previsao_atualizada", "realizada"]
        ].sum()
    )
