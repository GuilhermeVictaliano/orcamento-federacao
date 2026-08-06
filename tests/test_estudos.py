"""Testes dos estudos econômicos: estrutura do resultado e detecção correta de sinais construídos."""

import pandas as pd

from analise.estudos import (
    estudo_ciclo_politico,
    estudo_concentracao_receita,
    estudo_desigualdade_per_capita,
    estudo_passthrough_juros,
    estudo_rigidez,
    estudo_sustentabilidade,
)

CAMPOS_OBRIGATORIOS = {
    "titulo", "hipotese", "metodo", "formula_latex", "referencia",
    "estatisticas", "veredito", "interpretacao", "ressalvas", "severidade",
}


def _estrutura_ok(estudo):
    assert CAMPOS_OBRIGATORIOS <= set(estudo), f"faltam campos: {CAMPOS_OBRIGATORIOS - set(estudo)}"
    assert estudo["ressalvas"], "todo estudo deve declarar limitações"
    assert estudo["severidade"] in {"alerta", "atencao", "info", "positivo"}


# --- Estudo 1: sustentabilidade ----------------------------------------------

def test_sustentabilidade_detecta_beta_construido():
    # Constrói despesa = receita^1.2 ⇒ elasticidade verdadeira β = 1.2
    anos = list(range(2015, 2025))
    receita = {a: 100.0 * (1.05 ** (a - 2015)) for a in anos}
    despesa = {a: receita[a] ** 1.2 for a in anos}
    r = estudo_sustentabilidade({"Teste": despesa}, {"Teste": receita})
    _estrutura_ok(r)
    beta = r["estatisticas"].iloc[0]["β (elasticidade)"]
    assert abs(beta - 1.2) < 0.01, f"β estimado {beta} deveria recuperar 1.2"
    assert "Teste" in r["veredito"]
    assert r["severidade"] == "atencao"


def test_sustentabilidade_ente_conservador():
    anos = list(range(2015, 2025))
    receita = {a: 100.0 * (1.05 ** (a - 2015)) for a in anos}
    despesa = {a: receita[a] ** 0.8 for a in anos}   # β = 0.8
    r = estudo_sustentabilidade({"Prudente": despesa}, {"Prudente": receita})
    assert r["estatisticas"].iloc[0]["Leitura"] == "conservador"
    assert r["severidade"] == "positivo"


def test_sustentabilidade_serie_curta_e_ignorada():
    r = estudo_sustentabilidade({"X": {2023: 10.0, 2024: 11.0}}, {"X": {2023: 10.0, 2024: 11.0}})
    assert r["estatisticas"].empty


# --- Estudo 2: ciclo político -------------------------------------------------

def test_ciclo_politico_detecta_efeito_forte():
    # Municipal: anos eleitorais 2016/2020/2024 com crescimento muito maior
    serie = {a: (0.30 if a in (2016, 2020, 2024) else 0.01) for a in range(2016, 2025)}
    r = estudo_ciclo_politico({"Cidade": serie}, {"Cidade": "municipal"}, n_perm=2000)
    _estrutura_ok(r)
    assert r["teste"]["p_valor"] < 0.05
    assert r["severidade"] == "alerta"
    assert "significativa" in r["veredito"]


def test_ciclo_politico_sem_efeito_nao_rejeita():
    serie = {a: 0.05 for a in range(2016, 2025)}   # crescimento constante
    r = estudo_ciclo_politico({"Cidade": serie}, {"Cidade": "municipal"}, n_perm=2000)
    assert r["teste"]["p_valor"] > 0.05
    assert "Não há evidência" in r["veredito"] or "sem significância" in r["veredito"]


# --- Estudo 3: rigidez --------------------------------------------------------

def test_rigidez_calcula_fracao_correta():
    df = pd.DataFrame([
        {"ente": "A", "funcao": "Previdência Social", "realizado": 30.0},
        {"ente": "A", "funcao": "Encargos Especiais", "realizado": 30.0},
        {"ente": "A", "funcao": "Saúde", "realizado": 40.0},
    ])
    r = estudo_rigidez(df)
    _estrutura_ok(r)
    linha = r["estatisticas"].iloc[0]
    assert linha["Rigidez"] == "60.0%"
    assert linha["Espaço fiscal"] == "40.0%"
    assert r["severidade"] == "atencao"   # >= 50%


# --- Estudo 4: HHI de receita -------------------------------------------------

def test_concentracao_receita_hhi():
    df = pd.DataFrame([
        {"ente": "Concentrado", "categoria": "Tributária", "realizada": 90.0},
        {"ente": "Concentrado", "categoria": "Transferências", "realizada": 10.0},
        {"ente": "Diverso", "categoria": "Tributária", "realizada": 25.0},
        {"ente": "Diverso", "categoria": "Transferências", "realizada": 25.0},
        {"ente": "Diverso", "categoria": "Patrimonial", "realizada": 25.0},
        {"ente": "Diverso", "categoria": "Serviços", "realizada": 25.0},
    ])
    r = estudo_concentracao_receita(df)
    _estrutura_ok(r)
    tabela = r["estatisticas"].set_index("Ente")
    assert tabela.loc["Concentrado", "HHI"] == 0.82        # 0.9² + 0.1²
    assert tabela.loc["Diverso", "HHI"] == 0.25            # 4 × 0.25²
    assert tabela.loc["Concentrado", "Concentração"] == "alta"


# --- Estudo 5: Gini per capita ------------------------------------------------

def test_desigualdade_per_capita():
    despesa = {"Rico": {2024: 1000.0}, "Pobre": {2024: 100.0}}
    pops = {"Rico": 100, "Pobre": 100}     # 10 vs 1 por habitante
    r = estudo_desigualdade_per_capita(despesa, pops, 2024)
    _estrutura_ok(r)
    assert "Gini" in r["veredito"]
    assert len(r["estatisticas"]) == 2


def test_desigualdade_igualdade_perfeita():
    despesa = {"A": {2024: 100.0}, "B": {2024: 200.0}}
    pops = {"A": 100, "B": 200}            # ambos 1,0 por habitante
    r = estudo_desigualdade_per_capita(despesa, pops, 2024)
    assert "0.000" in r["veredito"]


# --- Estudo 6: pass-through ---------------------------------------------------

def test_passthrough_detecta_efeito_contemporaneo():
    # Série NÃO monotônica (se fosse linear no tempo, toda defasagem correlacionaria 1,0).
    valores = [1.0, 5.0, 2.0, 8.0, 3.0, 9.0, 4.0, 7.0]
    anos = list(range(2015, 2015 + len(valores)))
    selic = dict(zip(anos, valores))
    encargos = {a: 0.01 * selic[a] for a in anos}          # efeito no mesmo ano
    r = estudo_passthrough_juros(selic, encargos)
    _estrutura_ok(r)
    assert r["correlacao"]["melhor_rho"] > 0.99
    assert r["correlacao"]["melhor_lag"] == 0


def test_passthrough_detecta_efeito_defasado():
    # encargos do ano t+1 respondem à Selic do ano t ⇒ melhor defasagem = 1
    valores = [1.0, 5.0, 2.0, 8.0, 3.0, 9.0, 4.0, 7.0]
    anos = list(range(2015, 2015 + len(valores)))
    selic = dict(zip(anos, valores))
    encargos = {anos[0]: 0.05}
    for i in range(1, len(anos)):
        encargos[anos[i]] = 0.01 * valores[i - 1]
    r = estudo_passthrough_juros(selic, encargos)
    assert r["correlacao"]["melhor_lag"] == 1
    assert r["correlacao"]["melhor_rho"] > 0.99


def test_passthrough_serie_insuficiente():
    r = estudo_passthrough_juros({2024: 10.0}, {2024: 0.4})
    assert r["correlacao"] == {}
    assert "insuficiente" in r["veredito"]
