"""Restos a pagar por Poder, a partir do RREO-Anexo 07.

IMPORTANTE: este é o único recorte por Poder uniforme entre os entes no RREO
bimestral. Ele mede **restos a pagar** (obrigações de exercícios anteriores ainda
não quitadas), NÃO a despesa total executada por Poder — essa quebra não existe
no RREO. A página deixa isso explícito.

O valor por Poder é a linha com `cod_conta == 'SaldoTotal'` (exceto intra) e a
coluna "Saldo Total L = (e + k)", que consolida restos processados + não
processados a pagar.

O nome do Poder vem no campo `conta`. Para não depender de acentuação (a API às
vezes tem problemas de encoding), identificamos os Poderes principais por serem
MAIÚSCULOS e começarem por um prefixo conhecido — isso também exclui os sub-órgãos
(ex.: "Justiça Federal", em Title Case) e as linhas de subtotal/total.
"""

import pandas as pd

COD_SALDO_TOTAL = "SaldoTotal"
COLUNA_SALDO_TOTAL = "Saldo Total L = (e + k)"

# Ordem canônica de exibição dos Poderes.
ORDEM_PODERES = ["Executivo", "Legislativo", "Judiciário", "Ministério Público", "Defensoria Pública"]

COLUNAS_SAIDA = ["ente", "nivel", "poder", "restos_a_pagar"]


def _mapear_poder(conta: str) -> str | None:
    """Mapeia o texto de `conta` para um Poder canônico, ou None se não for um
    Poder principal (sub-órgão, subtotal, etc.)."""
    if not isinstance(conta, str):
        return None
    c = conta.strip()
    if not c.isupper():  # sub-órgãos vêm em Title Case
        return None
    if c.startswith("PODER EXECUTIVO"):
        return "Executivo"
    if c.startswith("PODER LEGISLATIVO"):
        return "Legislativo"
    if c.startswith("PODER JUDICI"):
        return "Judiciário"
    if c.startswith("MINIST"):
        return "Ministério Público"
    if c.startswith("DEFENSORIA"):
        return "Defensoria Pública"
    return None


def normalizar_restos_por_poder(df_bruto: pd.DataFrame, nome_ente: str, nivel: str) -> pd.DataFrame:
    """Uma linha por Poder com o saldo total de restos a pagar (exceto intra)."""
    if df_bruto.empty or "cod_conta" not in df_bruto.columns:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df = df_bruto[
        (df_bruto["cod_conta"] == COD_SALDO_TOTAL)
        & (df_bruto["coluna"] == COLUNA_SALDO_TOTAL)
    ].copy()
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df["poder"] = df["conta"].map(_mapear_poder)
    df = df[df["poder"].notna()]
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    tabela = df.groupby("poder", as_index=False)["valor"].sum().rename(columns={"valor": "restos_a_pagar"})
    tabela.insert(0, "nivel", nivel)
    tabela.insert(0, "ente", nome_ente)
    return tabela[COLUNAS_SAIDA]


def normalizar_restos_varios(dados_por_ente: dict) -> pd.DataFrame:
    """dados_por_ente: {chave: {"df": DataFrame bruto do Anexo 07, "nome": str, "nivel": str}}."""
    tabelas = [
        normalizar_restos_por_poder(info["df"], info["nome"], info["nivel"])
        for info in dados_por_ente.values()
    ]
    tabelas = [t for t in tabelas if not t.empty]
    if not tabelas:
        return pd.DataFrame(columns=COLUNAS_SAIDA)
    return pd.concat(tabelas, ignore_index=True)
