import pandas as pd

from analise.insights import (
    classificar_dependencia,
    dependencia_transferencias,
    destaques,
    per_capita,
    populacoes_validas,
    variacao_real,
)


def test_populacoes_validas_descarta_uniao_e_zeros():
    pops = {"União": 8_569_324, "Santos": 414_029, "Campinas": 1_170_247, "Fantasma": 0}
    validas = populacoes_validas(pops)
    assert "União" not in validas  # população federal é inconfiável na fonte
    assert "Fantasma" not in validas
    assert validas == {"Santos": 414_029, "Campinas": 1_170_247}


def test_per_capita():
    valores = {"Santos": 4_392_000_000.0, "Campinas": 8_240_000_000.0}
    pops = {"Santos": 414_029, "Campinas": 1_170_247}
    pc = per_capita(valores, pops)
    assert round(pc["Santos"]) == round(4_392_000_000.0 / 414_029)
    assert pc["Santos"] > pc["Campinas"]  # Santos gasta mais por habitante


def _rec(ente, categoria, valor):
    return {"ente": ente, "nivel": "municipal", "categoria": categoria, "realizada": valor}


def test_dependencia_transferencias():
    df = pd.DataFrame([
        _rec("Guarulhos", "Transferências correntes", 51.0),
        _rec("Guarulhos", "Tributária (impostos, taxas)", 32.0),
        _rec("Guarulhos", "Outras correntes", 17.0),
    ])
    dep = dependencia_transferencias(df).set_index("ente")
    assert round(dep.loc["Guarulhos", "pct_transferencias"], 2) == 0.51
    assert round(dep.loc["Guarulhos", "pct_tributaria"], 2) == 0.32


def test_classificar_dependencia_semaforo():
    assert classificar_dependencia(0.55)["severidade"] == "alerta"    # >50%
    assert classificar_dependencia(0.40)["severidade"] == "atencao"   # 30-50%
    assert classificar_dependencia(0.20)["severidade"] == "positivo"  # <30%
    assert classificar_dependencia(None)["severidade"] == "info"


def test_variacao_real_deflaciona_e_ordena():
    # fator_ini=1.5 (ano antigo vale mais em reais de hoje), fator_fim=1.0
    ini = {"Assistência Social": 100.0, "Energia": 100.0}
    fim = {"Assistência Social": 300.0, "Energia": 60.0}
    v = variacao_real(ini, fim, fator_ini=1.5, fator_fim=1.0, valor_minimo=0)
    # Assistência: real_ini=150, real_fim=300 -> +100%; Energia: 150->60 -> -60%
    assert v[0]["funcao"] == "Assistência Social"
    assert round(v[0]["variacao"], 2) == 1.00
    assert round(v[-1]["variacao"], 2) == -0.60


def test_variacao_real_ignora_ruido_abaixo_do_minimo():
    ini = {"Grande": 2e9, "Pequena": 1e6}
    fim = {"Grande": 3e9, "Pequena": 5e6}
    v = variacao_real(ini, fim, 1.0, 1.0, valor_minimo=1e9)
    assert [d["funcao"] for d in v] == ["Grande"]


def test_destaques_gera_frases_com_severidade():
    despesa = pd.DataFrame([
        {"ente": "Santos", "funcao": "Previdência Social", "realizado": 200.0, "previsao_atualizada": 200.0},
        {"ente": "Santos", "funcao": "Saúde", "realizado": 800.0, "previsao_atualizada": 800.0},
        {"ente": "Guarulhos", "funcao": "Saúde", "realizado": 500.0, "previsao_atualizada": 500.0},
    ])
    receita = pd.DataFrame([
        _rec("Guarulhos", "Transferências correntes", 51.0),
        _rec("Guarulhos", "Tributária (impostos, taxas)", 32.0),
    ])
    pops = {"União": 8_569_324, "Santos": 414_029, "Guarulhos": 1_383_272}
    achados = destaques(despesa, receita, pops)
    assert achados  # gerou ao menos um destaque
    assert all({"icone", "titulo", "texto", "severidade"} <= set(a) for a in achados)
    # deve mencionar a dependência de Guarulhos
    assert any("Guarulhos" in a["texto"] and "depende" in a["texto"] for a in achados)
