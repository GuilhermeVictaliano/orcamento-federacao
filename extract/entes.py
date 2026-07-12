"""Cadastro de entes da federação via SICONFI (/entes).

Usado para validar os códigos fixos em extract.config.ENTES_MVP e, no futuro,
resolver programaticamente novos entes sem precisar fixá-los no código.
"""

from pathlib import Path

import pandas as pd
import requests

from extract.config import BASE_URL

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def buscar_entes(exercicio: int, forcar_atualizacao: bool = False) -> pd.DataFrame:
    """Retorna o cadastro de entes (cod_ibge, nome, esfera, uf) de um exercício."""
    caminho = CACHE_DIR / f"entes_{exercicio}.parquet"

    if caminho.exists() and not forcar_atualizacao:
        return pd.read_parquet(caminho)

    url = f"{BASE_URL}/entes"
    resposta = requests.get(url, params={"an_exercicio": exercicio}, timeout=30)
    resposta.raise_for_status()
    df = pd.DataFrame(resposta.json().get("items", []))

    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not df.empty:
        df.to_parquet(caminho, index=False)

    return df


def validar_id_ente(id_ente: int, exercicio: int) -> bool:
    """Confirma que um id_ente (cod_ibge) existe no cadastro oficial do exercício."""
    df = buscar_entes(exercicio)
    return int(id_ente) in df["cod_ibge"].astype(int).values
