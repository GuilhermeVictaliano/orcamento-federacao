"""Extração de séries macroeconômicas do Banco Central (API SGS, sem token).

Usada como contexto financeiro do painel: a taxa Selic pressiona diretamente o
serviço da dívida (Encargos Especiais) do setor público.

API: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json
Série 432 = Selic meta (% a.a.), valor diário. Agregamos em média anual.
"""

from pathlib import Path

import pandas as pd
import requests

CACHE = Path(__file__).resolve().parent.parent / "data" / "raw" / "selic_media_anual.parquet"
SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
SERIE_SELIC_META = 432


def _num(valor) -> float | None:
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def selic_media_anual(ano_inicial: int, ano_final: int, forcar_atualizacao: bool = False) -> dict[int, float]:
    """Média anual da Selic meta (% a.a.) entre os anos dados. {ano: media}.

    Cacheada em Parquet; se a API do BCB falhar e não houver cache, retorna {}.
    """
    if CACHE.exists() and not forcar_atualizacao:
        try:
            df = pd.read_parquet(CACHE)
            cache = dict(zip(df["ano"].astype(int), df["selic"]))
            if all(a in cache for a in range(ano_inicial, ano_final + 1)):
                return cache
        except Exception:
            pass

    # A API do BCB aceita no máximo ~10 anos por requisição — buscamos em janelas.
    registros = []
    try:
        inicio = ano_inicial
        while inicio <= ano_final:
            fim = min(inicio + 9, ano_final)
            resposta = requests.get(
                SGS_URL.format(codigo=SERIE_SELIC_META),
                params={"formato": "json", "dataInicial": f"01/01/{inicio}", "dataFinal": f"31/12/{fim}"},
                timeout=40,
            )
            resposta.raise_for_status()
            registros.extend(resposta.json())
            inicio = fim + 1
    except Exception:
        if not registros:
            return {}

    por_ano: dict[int, list] = {}
    for r in registros:
        data = r.get("data", "")
        val = _num(r.get("valor"))
        if len(data) == 10 and val is not None:
            ano = int(data[-4:])
            por_ano.setdefault(ano, []).append(val)
    medias = {ano: round(sum(v) / len(v), 2) for ano, v in por_ano.items() if v}

    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"ano": list(medias), "selic": list(medias.values())}).to_parquet(CACHE, index=False)
    except Exception:
        pass

    return medias
