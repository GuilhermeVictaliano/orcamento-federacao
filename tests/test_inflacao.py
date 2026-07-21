import pandas as pd

from extract.inflacao import deflacionar, fatores_para_base


def test_fatores_para_base_normaliza_no_ano_base():
    indices = {2020: 100.0, 2021: 110.0, 2022: 121.0}
    fatores = fatores_para_base(indices, ano_base=2022)
    assert fatores[2022] == 1.0
    assert round(fatores[2021], 4) == round(121.0 / 110.0, 4)  # 1.1
    assert round(fatores[2020], 4) == 1.21


def test_fatores_para_base_ano_base_ausente():
    assert fatores_para_base({2020: 100.0}, ano_base=2030) == {}


def test_deflacionar_converte_para_reais_do_ano_base():
    indices = {2020: 100.0, 2022: 121.0}
    fatores = fatores_para_base(indices, ano_base=2022)
    # R$ 100 de 2020 valem R$ 121 em reais de 2022 (21% de inflação acumulada)
    assert round(deflacionar(100.0, 2020, fatores), 2) == 121.0
    assert deflacionar(100.0, 2022, fatores) == 100.0


def test_deflacionar_sem_fator_retorna_valor_original():
    fatores = {2022: 1.0}
    assert deflacionar(500.0, 1999, fatores) == 500.0


def test_deflacionar_preserva_nulo():
    assert pd.isna(deflacionar(None, 2020, {2020: 1.0}))
