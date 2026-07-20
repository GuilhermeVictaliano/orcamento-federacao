"""Extração do RREO (Relatório Resumido da Execução Orçamentária) via API do SICONFI.

A API pode ficar fora do ar (já houve manutenções emergenciais no Tesouro), então
toda consulta é salva em cache local (Parquet) e lida de lá nas próximas vezes.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from extract.config import BASE_URL, ANEXO_DESPESA_POR_FUNCAO

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def caminho_cache(id_ente: int, exercicio: int, bimestre: int, anexo: str = ANEXO_DESPESA_POR_FUNCAO) -> Path:
    anexo_slug = anexo.lower().replace(" ", "_")
    nome = f"rreo_{id_ente}_{exercicio}_{bimestre}_{anexo_slug}.parquet"
    return CACHE_DIR / nome


def data_atualizacao(
    id_ente: int, exercicio: int, bimestre: int, anexo: str = ANEXO_DESPESA_POR_FUNCAO
) -> datetime | None:
    """Data/hora em que este ente/período foi baixado pela última vez (mtime do cache)."""
    caminho = caminho_cache(id_ente, exercicio, bimestre, anexo)
    if not caminho.exists():
        return None
    return datetime.fromtimestamp(caminho.stat().st_mtime)


def baixar_rreo(
    id_ente: int,
    exercicio: int,
    bimestre: int,
    anexo: str = ANEXO_DESPESA_POR_FUNCAO,
    forcar_atualizacao: bool = False,
) -> pd.DataFrame:
    """Retorna o RREO de um ente/exercício/bimestre, usando cache local quando disponível.

    Se a API estiver fora do ar e não houver cache, propaga a exceção de rede;
    quem chama decide como sinalizar isso na interface (ex.: "dado indisponível").
    """
    caminho = caminho_cache(id_ente, exercicio, bimestre, anexo)

    if caminho.exists() and not forcar_atualizacao:
        return pd.read_parquet(caminho)

    df = _consultar_rreo_paginado(id_ente, exercicio, bimestre, anexo)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not df.empty:
        df.to_parquet(caminho, index=False)

    return df


def ultimo_bimestre_publicado(
    id_ente: int, exercicio: int, anexo: str = ANEXO_DESPESA_POR_FUNCAO
) -> int | None:
    """Maior bimestre (1..6) que já tem dado publicado para o ente/exercício.

    Testa do 6º para o 1º e retorna o primeiro com dado (cache local conta como
    dado). Útil para o ano corrente, cujo fechamento ainda não saiu. Retorna None
    se nenhum bimestre tiver dado (ex.: ano sem declaração ou API fora do ar).
    """
    for bimestre in range(6, 0, -1):
        caminho = caminho_cache(id_ente, exercicio, bimestre, anexo)
        if caminho.exists():
            return bimestre
        try:
            if not _consultar_rreo_paginado(id_ente, exercicio, bimestre, anexo, limite_sonda=1).empty:
                return bimestre
        except Exception:
            continue
    return None


def _consultar_rreo_paginado(
    id_ente: int, exercicio: int, bimestre: int, anexo: str, limite_sonda: int | None = None
) -> pd.DataFrame:
    """Consulta o RREO na API. Se `limite_sonda` for dado, faz uma única chamada
    leve (sem paginar) só para verificar se há dado — usado por
    `ultimo_bimestre_publicado`.
    """
    url = f"{BASE_URL}/rreo"
    params = {
        "id_ente": id_ente,
        "an_exercicio": exercicio,
        "nr_periodo": bimestre,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": anexo,
        "limit": limite_sonda if limite_sonda is not None else 5000,
        "offset": 0,
    }

    if limite_sonda is not None:
        resposta = requests.get(url, params=params, timeout=30)
        resposta.raise_for_status()
        return pd.DataFrame(resposta.json().get("items", []))

    registros = []
    while True:
        resposta = requests.get(url, params=params, timeout=60)
        resposta.raise_for_status()
        dados = resposta.json()

        items = dados.get("items", [])
        registros.extend(items)

        if not dados.get("hasMore", False):
            break
        params["offset"] += len(items)

    return pd.DataFrame(registros)
