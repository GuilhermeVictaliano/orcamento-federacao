import pandas as pd

from extract import rreo


class RespostaFalsa:
    """Simula requests.Response só com o necessário para os testes."""

    def __init__(self, items, has_more):
        self._items = items
        self._has_more = has_more

    def raise_for_status(self):
        pass

    def json(self):
        return {"items": self._items, "hasMore": self._has_more}


def test_baixar_rreo_pagina_ate_o_fim(tmp_path, monkeypatch):
    monkeypatch.setattr(rreo, "CACHE_DIR", tmp_path)

    paginas = [
        RespostaFalsa([{"conta": "Saúde", "valor": 100}], True),
        RespostaFalsa([{"conta": "Educação", "valor": 200}], False),
    ]

    chamadas = {"n": 0}

    def get_falso(url, params, timeout):
        resposta = paginas[chamadas["n"]]
        chamadas["n"] += 1
        return resposta

    monkeypatch.setattr(rreo.requests, "get", get_falso)

    df = rreo.baixar_rreo(id_ente=3550308, exercicio=2024, bimestre=6)

    assert chamadas["n"] == 2
    assert len(df) == 2
    assert set(df["conta"]) == {"Saúde", "Educação"}


def test_baixar_rreo_usa_cache_sem_chamar_api(tmp_path, monkeypatch):
    monkeypatch.setattr(rreo, "CACHE_DIR", tmp_path)

    caminho_cache = tmp_path / "rreo_1_2024_6_rreo-anexo_02.parquet"
    caminho_cache.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"conta": "Legislativa", "valor": 10}]).to_parquet(caminho_cache)

    def get_falso(*args, **kwargs):
        raise AssertionError("não deveria chamar a API quando há cache")

    monkeypatch.setattr(rreo.requests, "get", get_falso)

    df = rreo.baixar_rreo(id_ente=1, exercicio=2024, bimestre=6)

    assert len(df) == 1
    assert df.iloc[0]["conta"] == "Legislativa"


def test_baixar_rreo_forcar_atualizacao_ignora_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(rreo, "CACHE_DIR", tmp_path)

    caminho_cache = tmp_path / "rreo_1_2024_6_rreo-anexo_02.parquet"
    caminho_cache.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"conta": "Antigo", "valor": 1}]).to_parquet(caminho_cache)

    def get_falso(url, params, timeout):
        return RespostaFalsa([{"conta": "Novo", "valor": 2}], False)

    monkeypatch.setattr(rreo.requests, "get", get_falso)

    df = rreo.baixar_rreo(id_ente=1, exercicio=2024, bimestre=6, forcar_atualizacao=True)

    assert df.iloc[0]["conta"] == "Novo"
