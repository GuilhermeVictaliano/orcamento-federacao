import pandas as pd

from extract import entes
from extract.config import ENTES_MVP


def test_validar_id_ente_encontrado(tmp_path, monkeypatch):
    monkeypatch.setattr(entes, "CACHE_DIR", tmp_path)

    def get_falso(url, params, timeout):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"items": [{"cod_ibge": 1, "ente": "União", "esfera": "U"}]}

        return Resp()

    monkeypatch.setattr(entes.requests, "get", get_falso)

    assert entes.validar_id_ente(1, 2024) is True
    assert entes.validar_id_ente(999999, 2024) is False


def test_entes_mvp_tem_niveis_validos():
    niveis_validos = {"federal", "estadual", "municipal"}
    for chave, dados in ENTES_MVP.items():
        assert dados["nivel"] in niveis_validos
        assert isinstance(dados["id_ente"], int)
