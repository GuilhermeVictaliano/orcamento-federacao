import pandas as pd

from transform.fiscal import (
    classificar_saldo,
    peso_por_funcao,
    resultado_orcamentario,
    tendencia,
)


def _despesa(ente, funcao, realizado):
    return {"ente": ente, "funcao": funcao, "realizado": realizado}


def test_peso_por_funcao_calcula_fatia():
    df = pd.DataFrame(
        [
            _despesa("União", "Previdência Social", 300.0),
            _despesa("União", "Saúde", 700.0),
            _despesa("Campinas", "Previdência Social", 50.0),
            _despesa("Campinas", "Saúde", 50.0),
        ]
    )
    resultado = peso_por_funcao(df, "Previdência Social").set_index("ente")
    assert resultado.loc["União", "peso"] == 0.3
    assert resultado.loc["Campinas", "peso"] == 0.5


def test_peso_por_funcao_ente_sem_a_funcao_da_zero():
    df = pd.DataFrame([_despesa("Sorocaba", "Saúde", 100.0)])
    resultado = peso_por_funcao(df, "Previdência Social").set_index("ente")
    assert resultado.loc["Sorocaba", "peso"] == 0.0


def test_resultado_orcamentario_superavit_e_deficit():
    receita = pd.Series({"União": 1000.0, "Campinas": 80.0})
    despesa = pd.Series({"União": 900.0, "Campinas": 100.0})
    r = resultado_orcamentario(receita, despesa).set_index("ente")
    assert r.loc["União", "saldo"] == 100.0
    assert r.loc["Campinas", "saldo"] == -20.0


def test_classificar_saldo():
    assert classificar_saldo(10.0)["rotulo"] == "Superávit"
    assert classificar_saldo(-10.0)["rotulo"] == "Déficit"
    assert classificar_saldo(None)["rotulo"] == "Sem dado"


def test_tendencia_direcao():
    assert tendencia(0.32, 0.28)["rotulo"] == "subindo"
    assert tendencia(0.28, 0.33)["rotulo"] == "recuando"
    assert tendencia(0.30, 0.302)["rotulo"] == "estável"
    assert tendencia(0.30, None)["delta"] is None
