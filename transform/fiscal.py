"""Indicadores de saúde fiscal ("o governo está apertado?").

Trabalha sobre tabelas que já temos (despesa por função — Anexo 02 — e receita —
Anexo 01), evitando o Anexo 14 (RPPS), cuja estrutura é inconsistente entre entes
(muitos municípios não têm regime próprio de previdência).

Sinais de aperto, todos uniformes entre os 5 entes:
- Peso da Previdência Social na despesa (fatia crescente = pressão estrutural).
- Peso dos Encargos Especiais (juros/amortização da dívida e sentenças judiciais —
  onde entram os precatórios) = rigidez orçamentária.
- Resultado orçamentário no período (receita realizada − despesa liquidada).

Os precatórios em si não têm API pública consolidada (o CNJ só publica painel);
eles aparecem parcialmente dentro de "Encargos Especiais" / subfunção "Sentenças
Judiciais". Aqui usamos Encargos Especiais como proxy de rigidez, sem prometer o
estoque completo de precatórios.
"""

import pandas as pd

FUNCAO_PREVIDENCIA = "Previdência Social"
FUNCAO_ASSISTENCIA = "Assistência Social"
FUNCAO_ENCARGOS = "Encargos Especiais"


def peso_por_funcao(tabela_despesa: pd.DataFrame, funcao: str) -> pd.DataFrame:
    """Fatia (%) da despesa realizada de cada ente que foi para uma função.

    Retorna colunas: ente, realizado_funcao, total_ente, peso.
    """
    colunas = ["ente", "realizado_funcao", "total_ente", "peso"]
    if tabela_despesa.empty:
        return pd.DataFrame(columns=colunas)

    total = tabela_despesa.groupby("ente")["realizado"].sum()
    da_funcao = (
        tabela_despesa[tabela_despesa["funcao"] == funcao]
        .groupby("ente")["realizado"].sum()
    )
    linhas = []
    for ente, tot in total.items():
        rf = float(da_funcao.get(ente, 0.0))
        linhas.append(
            {"ente": ente, "realizado_funcao": rf, "total_ente": float(tot), "peso": (rf / tot) if tot else None}
        )
    return pd.DataFrame(linhas, columns=colunas)


def resultado_orcamentario(receita_por_ente: pd.Series, despesa_por_ente: pd.Series) -> pd.DataFrame:
    """Saldo (receita realizada − despesa liquidada) por ente, no período.

    receita_por_ente / despesa_por_ente: Series indexadas por nome do ente.
    Retorna colunas: ente, receita, despesa, saldo.
    """
    entes = sorted(set(receita_por_ente.index) & set(despesa_por_ente.index))
    linhas = [
        {
            "ente": ente,
            "receita": float(receita_por_ente[ente]),
            "despesa": float(despesa_por_ente[ente]),
            "saldo": float(receita_por_ente[ente]) - float(despesa_por_ente[ente]),
        }
        for ente in entes
    ]
    return pd.DataFrame(linhas, columns=["ente", "receita", "despesa", "saldo"])


def classificar_saldo(saldo) -> dict:
    """Semáforo objetivo do resultado orçamentário."""
    if saldo is None or pd.isna(saldo):
        return {"icone": "⚪", "rotulo": "Sem dado"}
    if saldo >= 0:
        return {"icone": "🟢", "rotulo": "Superávit"}
    return {"icone": "🔴", "rotulo": "Déficit"}


def tendencia(atual, anterior) -> dict:
    """Direção de um indicador entre dois períodos (ex.: peso da previdência).

    Para pesos/rigidez, "subindo" costuma indicar mais pressão fiscal — por isso a
    seta para cima usa tom de alerta.
    """
    if atual is None or anterior is None or pd.isna(atual) or pd.isna(anterior):
        return {"icone": "→", "rotulo": "sem base de comparação", "delta": None}
    delta = atual - anterior
    if abs(delta) < 0.005:  # meio ponto percentual
        return {"icone": "→", "rotulo": "estável", "delta": delta}
    if delta > 0:
        return {"icone": "🔺", "rotulo": "subindo", "delta": delta}
    return {"icone": "🔻", "rotulo": "recuando", "delta": delta}
