"""Helpers compartilhados entre as páginas do painel (home + app/pages/*).

Concentra formatação, carregamento cacheado de dados do SICONFI e enriquecimento
de percentuais, para que cada página não reimplemente o mesmo código.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app.cores import classificar_execucao
from extract.config import ANEXO_RECEITA, ANEXO_RESTOS_A_PAGAR, ENTES_MVP
from extract.rreo import baixar_rreo, data_atualizacao, ultimo_bimestre_publicado
from transform.normalizar import normalizar_varios
from transform.poderes import normalizar_restos_varios
from transform.receita import normalizar_receita_varios


def formatar_reais(valor) -> str:
    if pd.isna(valor):
        return "—"
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_pct(valor) -> str:
    if pd.isna(valor):
        return "—"
    return f"{valor:.1%}"


def botao_download_csv(df: pd.DataFrame, nome_arquivo: str, label: str = "⬇️ Baixar CSV") -> None:
    """Botão de download da tabela em CSV (utf-8-sig, separador ';' — abre bem no Excel BR)."""
    csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(label, data=csv, file_name=nome_arquivo, mime="text/csv")


def enriquecer_com_percentuais(tabela: pd.DataFrame, totais_por_ente: pd.Series) -> pd.DataFrame:
    """Adiciona: % do orçamento total do ente e % de execução (realizado / previsão atualizada),
    já com status (ícone + rótulo) classificado a partir do % de execução.
    """
    df = tabela.copy()
    df["proporcao"] = df.apply(
        lambda linha: (linha["realizado"] / totais_por_ente[linha["ente"]]) if totais_por_ente.get(linha["ente"]) else None,
        axis=1,
    )
    df["pct_execucao"] = df.apply(
        lambda linha: (linha["realizado"] / linha["previsao_atualizada"]) if linha["previsao_atualizada"] else None,
        axis=1,
    )
    status = df["pct_execucao"].map(classificar_execucao)
    df["status_icone"] = status.map(lambda s: s["icone"])
    df["status_rotulo"] = status.map(lambda s: s["rotulo"])
    return df


@st.cache_data(show_spinner="Carregando dados do SICONFI...")
def carregar_dados(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache local) o RREO-Anexo 02 de todos os entes do MVP e normaliza.

    Retorna a tabela normalizada, a lista de entes sem dado declarado no período e
    metadados de cada ente (linhas brutas baixadas, data da última sincronização).
    A API do SICONFI já teve instabilidades; se uma chamada falhar, o ente entra
    na lista de "sem dado" em vez de derrubar o app inteiro.
    """
    dados_por_ente = {}
    entes_sem_dado = []
    metadados_entes = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre)
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}
        metadados_entes.append(
            {
                "ente": info["nome"],
                "linhas_brutas": len(df_bruto),
                "atualizado_em": data_atualizacao(info["id_ente"], exercicio, bimestre),
            }
        )

    tabela = normalizar_varios(dados_por_ente)
    return tabela, entes_sem_dado, metadados_entes


@st.cache_data(show_spinner="Carregando receita do SICONFI...")
def carregar_receita(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache) o RREO-Anexo 01 (receita) de todos os entes e normaliza.

    Retorna a tabela de receita por categoria e a lista de entes sem dado no período.
    Mesmo padrão resiliente de `carregar_dados`: falha de um ente não derruba o app.
    """
    dados_por_ente = {}
    entes_sem_dado = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(
                id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre, anexo=ANEXO_RECEITA
            )
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}

    tabela = normalizar_receita_varios(dados_por_ente)
    return tabela, entes_sem_dado


@st.cache_data(show_spinner="Carregando restos a pagar por Poder...")
def carregar_restos_poder(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache) o RREO-Anexo 07 de todos os entes e normaliza por Poder.

    Retorna a tabela [ente, nivel, poder, restos_a_pagar] e a lista de entes sem dado.
    Mesmo padrão resiliente das demais cargas.
    """
    dados_por_ente = {}
    entes_sem_dado = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(
                id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre, anexo=ANEXO_RESTOS_A_PAGAR
            )
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}

    tabela = normalizar_restos_varios(dados_por_ente)
    return tabela, entes_sem_dado


@st.cache_data(show_spinner="Consultando contratos no PNCP...")
def carregar_contratos(cnpj: str, ano: int):
    """Baixa (ou lê do cache) e normaliza os contratos de um órgão (CNPJ) no ano.

    Retorna (tabela_normalizada, erro) — `erro` é None em caso de sucesso ou uma
    mensagem curta se a consulta ao PNCP falhar.
    """
    from extract.pncp import baixar_contratos
    from transform.contratos import normalizar_contratos

    try:
        bruto = baixar_contratos(cnpj=cnpj, ano=ano)
    except Exception as exc:
        return normalizar_contratos(pd.DataFrame()), f"Falha ao consultar o PNCP: {type(exc).__name__}"
    return normalizar_contratos(bruto), None


@st.cache_data(show_spinner=False)
def fatores_ipca(ano_base: int) -> dict:
    """Fatores de deflação (nominal→real em reais do ano-base) por ano, via IPCA/IBGE.

    Cacheado para não consultar a SIDRA a cada rerun.
    """
    from extract.inflacao import fatores_para_base, indice_ipca_anual

    return fatores_para_base(indice_ipca_anual(ano_base), ano_base)


@st.cache_data(show_spinner=False)
def bimestre_recente_uniao(exercicio: int) -> int:
    """Último bimestre publicado pela União no exercício (fallback = 6).

    Serve de default sensato para o ano corrente, cujo fechamento (6º bimestre)
    ainda não saiu. Cacheado para não sondar a API a cada rerun.
    """
    id_uniao = ENTES_MVP["uniao"]["id_ente"]
    bimestre = ultimo_bimestre_publicado(id_uniao, exercicio)
    return bimestre if bimestre is not None else 6


@st.cache_data(show_spinner="Montando série histórica de despesa...")
def serie_anual_despesa(anos: tuple[int, ...]) -> pd.DataFrame:
    """Total de despesa por ente para cada ano da série.

    Para anos fechados usa o acumulado do 6º bimestre; para o ano corrente usa o
    último bimestre publicado (marcado como `parcial=True`, pois não é comparável
    a um ano inteiro). Valores são NOMINAIS (não ajustados por inflação).
    """
    linhas = []
    for ano in anos:
        bim = bimestre_recente_uniao(ano)
        tabela, _, _ = carregar_dados(ano, bim)
        if tabela.empty:
            continue
        agg = tabela.groupby(["ente", "nivel"], as_index=False)[
            ["previsao_inicial", "previsao_atualizada", "realizado"]
        ].sum()
        agg["ano"] = ano
        agg["bimestre"] = bim
        agg["parcial"] = bim < 6
        linhas.append(agg)
    colunas = ["ente", "nivel", "ano", "bimestre", "parcial", "previsao_inicial", "previsao_atualizada", "realizado"]
    if not linhas:
        return pd.DataFrame(columns=colunas)
    return pd.concat(linhas, ignore_index=True)[colunas]


@st.cache_data(show_spinner="Montando série de pesos por função...")
def serie_peso_funcao(anos: tuple[int, ...], funcoes: tuple[str, ...]) -> pd.DataFrame:
    """Fatia (%) da despesa de cada ente nas funções dadas, ano a ano.

    Retorna: ente, nivel, ano, funcao, realizado, total_ente, peso, parcial.
    Usa o cache de despesa (Anexo 02) já aquecido pela série histórica.
    """
    colunas = ["ente", "nivel", "ano", "funcao", "realizado", "total_ente", "peso", "parcial"]
    linhas = []
    for ano in anos:
        bim = bimestre_recente_uniao(ano)
        tabela, _, _ = carregar_dados(ano, bim)
        if tabela.empty:
            continue
        total = tabela.groupby("ente")["realizado"].sum()
        sub = (
            tabela[tabela["funcao"].isin(funcoes)]
            .groupby(["ente", "nivel", "funcao"], as_index=False)["realizado"].sum()
        )
        if sub.empty:
            continue
        sub["ano"] = ano
        sub["total_ente"] = sub["ente"].map(total)
        sub["peso"] = sub.apply(
            lambda r: (r["realizado"] / r["total_ente"]) if r["total_ente"] else None, axis=1
        )
        sub["parcial"] = bim < 6
        linhas.append(sub)
    if not linhas:
        return pd.DataFrame(columns=colunas)
    return pd.concat(linhas, ignore_index=True)[colunas]


@st.cache_data(show_spinner="Montando série histórica de receita...")
def serie_anual_receita(anos: tuple[int, ...]) -> pd.DataFrame:
    """Total de receita realizada por ente para cada ano (mesma lógica de série da despesa)."""
    from transform.receita import totais_receita_por_ente

    linhas = []
    for ano in anos:
        bim = bimestre_recente_uniao(ano)
        tabela, _ = carregar_receita(ano, bim)
        if tabela.empty:
            continue
        agg = totais_receita_por_ente(tabela)
        agg["ano"] = ano
        agg["bimestre"] = bim
        agg["parcial"] = bim < 6
        linhas.append(agg)
    colunas = ["ente", "nivel", "ano", "bimestre", "parcial", "previsao_inicial", "previsao_atualizada", "realizada"]
    if not linhas:
        return pd.DataFrame(columns=colunas)
    return pd.concat(linhas, ignore_index=True)[colunas]
