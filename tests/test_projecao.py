from analise.projecao import (
    crescimento_vs_inflacao,
    erro_backtest,
    fracao_executada,
    projetar_ano,
    tendencia_linear,
)


def test_fracao_executada():
    parciais = {2022: 34.0, 2023: 26.0, 2024: 30.0}
    fechados = {2022: 100.0, 2023: 100.0, 2024: 100.0}
    saz = fracao_executada(parciais, fechados)
    assert round(saz["media"], 2) == 0.30
    assert saz["minimo"] == 0.26
    assert saz["maximo"] == 0.34


def test_projetar_ano_ponto_e_faixa():
    saz = {"media": 0.30, "minimo": 0.26, "maximo": 0.34}
    proj = projetar_ano(30.0, saz)
    assert round(proj["projecao"], 1) == 100.0        # 30 / 0.30
    # fração maior (0.34) => ano fecha menor; fração menor (0.26) => maior
    assert round(proj["minimo"], 1) == round(30 / 0.34, 1)
    assert round(proj["maximo"], 1) == round(30 / 0.26, 1)
    assert proj["minimo"] < proj["projecao"] < proj["maximo"]


def test_projetar_ano_sem_base():
    assert projetar_ano(30.0, {"media": None, "minimo": None, "maximo": None}) == {}


def test_erro_backtest_metodo_perfeito():
    # fração idêntica todo ano => erro zero
    parciais = {2021: 30.0, 2022: 30.0, 2023: 30.0}
    fechados = {2021: 100.0, 2022: 100.0, 2023: 100.0}
    assert erro_backtest(parciais, fechados) == 0.0


def test_erro_backtest_insuficiente():
    assert erro_backtest({2024: 30.0}, {2024: 100.0}) is None


def test_tendencia_linear_crescente():
    serie = {2020: 100.0, 2021: 110.0, 2022: 120.0, 2023: 130.0}
    t = tendencia_linear(serie)
    assert round(t["inclinacao"]) == 10          # +10/ano
    assert t["proximo_ano"] == 2024
    assert round(t["projecao_proximo_ano"]) == 140


def test_crescimento_vs_inflacao_real():
    serie = {2022: 100.0, 2023: 120.0}
    # fatores para base: 2022 vale 1.10 em reais de base, 2023 vale 1.0 (inflação de 10%)
    fatores = {2022: 1.10, 2023: 1.00}
    r = crescimento_vs_inflacao(serie, fatores)
    assert r[0]["ano"] == 2023
    assert round(r[0]["nominal"], 2) == 0.20     # +20% nominal
    # real: (120*1.0)/(100*1.10) - 1 = 120/110 - 1 ≈ +9%
    assert round(r[0]["real"], 3) == round(120 / 110 - 1, 3)
