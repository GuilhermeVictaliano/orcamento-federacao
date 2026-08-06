"""Testes das primitivas estatísticas contra resultados analiticamente conhecidos."""

import numpy as np

from analise.econometria import (
    coef_variacao,
    correlacao_defasada,
    gini,
    hhi,
    ols_simples,
    pearson,
    t_contra,
    teste_permutacao,
)


# --- OLS ---------------------------------------------------------------------

def test_ols_reta_perfeita_recupera_coeficientes():
    # y = 3 + 2x exatamente ⇒ β=2, α=3, R²=1, resíduos nulos
    x = [1, 2, 3, 4, 5]
    y = [3 + 2 * v for v in x]
    r = ols_simples(x, y)
    assert round(r["beta"], 10) == 2.0
    assert round(r["alpha"], 10) == 3.0
    assert round(r["r2"], 10) == 1.0
    assert abs(np.asarray(r["residuos"])).max() < 1e-9
    assert r["n"] == 5


def test_ols_sem_relacao_tem_beta_zero():
    # y constante ⇒ β=0 (x não explica nada)
    r = ols_simples([1, 2, 3, 4], [7, 7, 7, 7])
    assert round(r["beta"], 10) == 0.0


def test_ols_amostra_insuficiente_ou_x_constante():
    assert ols_simples([1, 2], [3, 4]) == {}          # n < 3
    assert ols_simples([5, 5, 5], [1, 2, 3]) == {}    # x sem variância


def test_t_contra_referencia():
    # β=1.2, SE=0.1 ⇒ t contra 1 é (1.2-1)/0.1 = 2
    assert round(t_contra(1.2, 0.1, 1.0), 10) == 2.0
    assert t_contra(1.2, None) is None
    assert t_contra(1.2, 0.0) is None


# --- Teste de permutação ------------------------------------------------------

def test_permutacao_grupos_identicos_nao_rejeita():
    # mesma distribuição ⇒ diferença ~0 e p alto (não rejeita H0)
    r = teste_permutacao([1, 2, 3, 4], [1, 2, 3, 4], n_perm=2000)
    assert abs(r["diferenca"]) < 1e-9
    assert r["p_valor"] > 0.5


def test_permutacao_grupos_muito_diferentes_rejeita():
    # separação total ⇒ p pequeno
    r = teste_permutacao([10, 11, 12, 13, 14], [1, 2, 3, 4, 5], n_perm=2000)
    assert r["diferenca"] > 0
    assert r["p_valor"] < 0.05


def test_permutacao_reprodutivel_com_semente_fixa():
    a, b = [5, 6, 7, 8], [1, 2, 3, 9]
    assert teste_permutacao(a, b, n_perm=1000)["p_valor"] == teste_permutacao(a, b, n_perm=1000)["p_valor"]


def test_permutacao_grupo_vazio():
    assert teste_permutacao([], [1, 2, 3]) == {}


# --- Correlação ---------------------------------------------------------------

def test_pearson_relacao_perfeita():
    assert round(pearson([1, 2, 3, 4], [2, 4, 6, 8]), 10) == 1.0      # positiva
    assert round(pearson([1, 2, 3, 4], [8, 6, 4, 2]), 10) == -1.0     # negativa


def test_pearson_sem_variancia_ou_amostra_curta():
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert pearson([1, 2], [3, 4]) is None


def test_correlacao_defasada_encontra_o_lag_certo():
    # y é x deslocado em 1 período ⇒ maior correlação no lag 1
    x = [1, 2, 3, 4, 5, 6]
    y = [0, 1, 2, 3, 4, 5]  # y[k+1] acompanha x[k]
    r = correlacao_defasada(x, y, max_lag=2)
    assert r["melhor_lag"] in (0, 1)
    assert abs(r["melhor_rho"]) > 0.9


# --- Gini ---------------------------------------------------------------------

def test_gini_igualdade_perfeita_e_zero():
    assert round(gini([10, 10, 10, 10]), 10) == 0.0


def test_gini_concentracao_extrema_tende_a_um():
    # um recebe tudo entre n=100 ⇒ G ≈ (n-1)/n = 0.99
    g = gini([100.0] + [0.0] * 99)
    assert 0.95 < g < 1.0


def test_gini_ordem_nao_importa_e_amostra_minima():
    assert round(gini([1, 3, 5]), 8) == round(gini([5, 1, 3]), 8)
    assert gini([5]) is None


# --- HHI ----------------------------------------------------------------------

def test_hhi_monopolio_e_um():
    r = hhi([100.0])
    assert round(r["hhi"], 10) == 1.0
    assert r["faixa"] == "alta"


def test_hhi_dez_partes_iguais_e_baixa_concentracao():
    r = hhi([10] * 10)              # cada um 10% ⇒ HHI = 10*(0.1²) = 0.10
    assert round(r["hhi"], 10) == 0.10
    assert r["faixa"] == "baixa"
    assert round(r["equivalente_partes_iguais"], 6) == 10.0


def test_hhi_faixa_moderada():
    r = hhi([10] * 5)               # 5 partes iguais ⇒ HHI = 0.20
    assert round(r["hhi"], 10) == 0.20
    assert r["faixa"] == "moderada"


def test_hhi_vazio():
    assert hhi([]) == {}


# --- Coeficiente de variação --------------------------------------------------

def test_coef_variacao():
    assert coef_variacao([5, 5, 5, 5]) == 0.0        # sem dispersão
    assert coef_variacao([1, 2, 3, 4]) > 0
    assert coef_variacao([7]) is None
