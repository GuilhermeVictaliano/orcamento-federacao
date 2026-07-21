"""Índice de inflação (IPCA) para corrigir séries históricas de valores nominais.

Fonte: IBGE via API SIDRA, tabela 1737 (IPCA número-índice, base dez/1993=100),
variável 2266. Usamos o índice de **dezembro** de cada ano para deflacionar valores
anuais; para o ano corrente (sem dezembro fechado) usamos o último mês disponível.

Deflação: valor_real(base) = valor_nominal(ano) × indice(base) / indice(ano).
Assim todos os anos ficam em reais do ano-base escolhido (por padrão, o mais recente).

Resiliência: os índices de anos fechados não mudam, então trazemos uma tabela
estática embutida (2015–2024) como fallback caso a SIDRA esteja fora do ar; a
busca ao vivo serve para acrescentar os anos mais recentes.
"""

from pathlib import Path

import pandas as pd
import requests

CACHE = Path(__file__).resolve().parent.parent / "data" / "raw" / "ipca_indice_anual.parquet"

SIDRA_URL = "https://apisidra.ibge.gov.br/values/t/1737/n1/1/v/2266/p/{periodo}"

# Índice IPCA de dezembro (base dez/1993=100), anos fechados. Fallback estático —
# valores de anos passados não mudam. Confirmados contra a SIDRA em 2026.
IPCA_DEZEMBRO_ESTATICO = {
    2015: 4493.17,
    2016: 4775.70,
    2017: 4916.46,
    2018: 5100.61,
    2019: 5320.25,
    2020: 5560.59,
    2021: 6120.04,
    2022: 6474.09,
    2023: 6773.27,
    2024: 7100.50,
}


def _buscar_indices_sidra(ano_inicial: int, ano_final: int) -> dict[int, float]:
    """Índice anual (dezembro, ou último mês do ano corrente) via SIDRA.

    Retorna {ano: indice}. Levanta exceção de rede se a API falhar.
    """
    periodo = f"{ano_inicial}01-{ano_final}12"
    resposta = requests.get(SIDRA_URL.format(periodo=periodo), timeout=40)
    resposta.raise_for_status()
    dados = resposta.json()

    por_mes: dict[str, float] = {}
    for linha in dados[1:]:  # linha 0 é o cabeçalho
        per = linha.get("D3C")  # AAAAMM
        val = linha.get("V")
        if not per or val in (None, "...", "-", ".."):
            continue
        try:
            por_mes[per] = float(val)
        except (TypeError, ValueError):
            continue

    # Reduz para um índice por ano: dezembro se houver, senão o mês mais recente.
    por_ano: dict[int, float] = {}
    for per, val in por_mes.items():
        ano = int(per[:4])
        por_ano.setdefault(ano, {})[int(per[4:])] = val
    return {ano: meses.get(12, meses[max(meses)]) for ano, meses in por_ano.items()}


def indice_ipca_anual(ano_final: int, forcar_atualizacao: bool = False) -> dict[int, float]:
    """Índice IPCA (dezembro/último mês) por ano, de 2015 até `ano_final`.

    Combina a busca ao vivo na SIDRA com o fallback estático; se a rede falhar,
    devolve pelo menos os anos estáticos. Cacheado localmente em Parquet.
    """
    if CACHE.exists() and not forcar_atualizacao:
        try:
            df = pd.read_parquet(CACHE)
            cache = dict(zip(df["ano"], df["indice"]))
            if ano_final in cache:  # cache cobre o ano pedido
                return cache
        except Exception:
            pass

    indices = dict(IPCA_DEZEMBRO_ESTATICO)
    try:
        indices.update(_buscar_indices_sidra(2015, ano_final))
    except Exception:
        pass  # mantém só o estático

    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"ano": list(indices), "indice": list(indices.values())}).to_parquet(CACHE, index=False)
    except Exception:
        pass

    return indices


def fatores_para_base(indices: dict[int, float], ano_base: int) -> dict[int, float]:
    """Fator multiplicativo que leva o valor nominal de cada ano a reais do ano-base."""
    base = indices.get(ano_base)
    if not base:
        return {}
    return {ano: (base / idx) for ano, idx in indices.items() if idx}


def deflacionar(valor, ano: int, fatores: dict[int, float]):
    """Converte um valor nominal do `ano` para reais do ano-base. Sem fator, retorna o valor."""
    if valor is None or pd.isna(valor):
        return valor
    fator = fatores.get(ano)
    return valor * fator if fator is not None else valor
