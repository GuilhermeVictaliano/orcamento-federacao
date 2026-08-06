"""Primitivas estatísticas para os estudos econômicos.

Implementadas com numpy puro, de propósito: a fórmula fica **visível e auditável**
no código, em vez de escondida numa biblioteca. Cada função documenta a expressão
matemática que aplica e a referência quando cabe.

Nenhuma dependência de scipy/statsmodels. Para significância usamos **teste de
permutação** (reamostragem), que não exige tabela de distribuição e é apropriado
para as amostras pequenas deste projeto (7 entes, ~10 anos).
"""

from __future__ import annotations

import numpy as np

SEMENTE_PADRAO = 42  # reprodutibilidade: mesmo p-valor a cada execução


def ols_simples(x, y) -> dict:
    """Regressão linear simples por mínimos quadrados ordinários: y = α + βx + ε.

    β = Σ(xᵢ-x̄)(yᵢ-ȳ) / Σ(xᵢ-x̄)²
    α = ȳ - βx̄
    R² = 1 - SQR/SQT, com SQR = Σ(yᵢ-ŷᵢ)² e SQT = Σ(yᵢ-ȳ)²
    SE(β) = √( σ̂² / Σ(xᵢ-x̄)² ), σ̂² = SQR/(n-2)
    t(β=b₀) = (β - b₀)/SE(β)

    Retorna {} se n < 3 ou se x não tiver variância.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < 3 or len(y) != n:
        return {}
    sxx = float(((x - x.mean()) ** 2).sum())
    if sxx == 0:
        return {}

    beta = float(((x - x.mean()) * (y - y.mean())).sum() / sxx)
    alpha = float(y.mean() - beta * x.mean())
    ajustado = alpha + beta * x
    residuos = y - ajustado
    sqr = float((residuos ** 2).sum())
    sqt = float(((y - y.mean()) ** 2).sum())
    r2 = float(1 - sqr / sqt) if sqt > 0 else None
    sigma2 = sqr / (n - 2)
    se_beta = float(np.sqrt(sigma2 / sxx)) if sigma2 >= 0 else None

    return {
        "alpha": alpha,
        "beta": beta,
        "r2": r2,
        "se_beta": se_beta,
        "n": int(n),
        "residuos": residuos,
    }


def t_contra(beta: float, se_beta: float | None, valor_referencia: float = 0.0) -> float | None:
    """Estatística t para H₀: β = valor_referencia. t = (β - b₀)/SE(β).

    Sem tabela de distribuição, usamos a regra prática |t| > 2 ≈ significativo a ~5%
    para amostras pequenas — e dizemos isso explicitamente na interface.
    """
    if se_beta is None or se_beta == 0:
        return None
    return float((beta - valor_referencia) / se_beta)


def teste_permutacao(a, b, n_perm: int = 10000, semente: int = SEMENTE_PADRAO) -> dict:
    """Teste não-paramétrico de diferença de médias por reamostragem.

    H₀: os dois grupos vêm da mesma distribuição (o rótulo não importa).
    Procedimento: embaralha os rótulos `n_perm` vezes e mede com que frequência a
    diferença de médias embaralhada é ao menos tão extrema quanto a observada.
    p = (1 + #{|dif_perm| ≥ |dif_obs|}) / (1 + n_perm)   [correção de Davison & Hinkley]

    Vantagem sobre o teste t aqui: não assume normalidade nem variâncias iguais, e
    é válido para n pequeno. Retorna {} se algum grupo estiver vazio.
    """
    a = np.asarray([v for v in a if v is not None], dtype=float)
    b = np.asarray([v for v in b if v is not None], dtype=float)
    if len(a) == 0 or len(b) == 0:
        return {}

    dif_obs = float(a.mean() - b.mean())
    juntos = np.concatenate([a, b])
    n_a = len(a)
    rng = np.random.default_rng(semente)

    extremos = 0
    for _ in range(n_perm):
        rng.shuffle(juntos)
        dif = juntos[:n_a].mean() - juntos[n_a:].mean()
        if abs(dif) >= abs(dif_obs):
            extremos += 1

    return {
        "diferenca": dif_obs,
        "media_a": float(a.mean()),
        "media_b": float(b.mean()),
        "n_a": int(n_a),
        "n_b": int(len(b)),
        "p_valor": float((1 + extremos) / (1 + n_perm)),
        "n_perm": int(n_perm),
    }


def pearson(x, y) -> float | None:
    """Coeficiente de correlação linear de Pearson: ρ = cov(x,y)/(σx·σy). None se n<3."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or len(y) != len(x):
        return None
    if x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def correlacao_defasada(x, y, max_lag: int = 2) -> dict:
    """Correlação de x com y defasado: corr(xₜ, yₜ₊ₖ) para k = 0..max_lag.

    Útil quando o efeito leva tempo para aparecer (ex.: juros hoje → serviço da
    dívida no ano seguinte). Retorna todas as defasagens e a de maior |ρ|.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    por_lag = {}
    for k in range(max_lag + 1):
        if len(x) - k < 3:
            continue
        rho = pearson(x[: len(x) - k] if k else x, y[k:] if k else y)
        if rho is not None:
            por_lag[k] = rho
    if not por_lag:
        return {}
    # Desempate por parcimônia: entre defasagens com correlação praticamente igual
    # (diferença < 1e-6), escolhe-se a menor — evita atribuir defasagem a um efeito
    # que já é contemporâneo.
    maior = max(abs(v) for v in por_lag.values())
    melhor = min(k for k, v in por_lag.items() if abs(abs(v) - maior) < 1e-6)
    return {"por_lag": por_lag, "melhor_lag": int(melhor), "melhor_rho": float(por_lag[melhor])}


def gini(valores) -> float | None:
    """Coeficiente de Gini (Gini, 1912) — desigualdade de uma distribuição.

    G = Σᵢ Σⱼ |xᵢ - xⱼ| / (2n²x̄)
    0 = igualdade perfeita; 1 = concentração máxima. None se n<2 ou soma nula.
    """
    x = np.asarray([v for v in valores if v is not None and v >= 0], dtype=float)
    n = len(x)
    if n < 2 or x.sum() == 0:
        return None
    dif_absolutas = np.abs(x[:, None] - x[None, :]).sum()
    return float(dif_absolutas / (2 * n * n * x.mean()))


def hhi(valores) -> dict:
    """Índice Herfindahl-Hirschman (Hirschman 1945; Herfindahl 1950).

    HHI = Σ sᵢ², com sᵢ = participação da parte i no total (0 a 1).
    Interpretação (faixas normalizadas do DOJ/FTC, convertidas para escala 0–1):
      < 0,15 = baixa concentração · 0,15–0,25 = moderada · > 0,25 = alta.
    Também devolve o equivalente em "número de partes iguais" (1/HHI).
    """
    x = np.asarray([v for v in valores if v is not None and v > 0], dtype=float)
    if len(x) == 0 or x.sum() == 0:
        return {}
    shares = x / x.sum()
    valor = float((shares ** 2).sum())
    faixa = "alta" if valor > 0.25 else ("moderada" if valor > 0.15 else "baixa")
    return {
        "hhi": valor,
        "faixa": faixa,
        "equivalente_partes_iguais": float(1 / valor) if valor else None,
        "n_partes": int(len(x)),
    }


def coef_variacao(valores) -> float | None:
    """Coeficiente de variação: CV = σ/|μ|. Mede volatilidade relativa (previsibilidade)."""
    x = np.asarray([v for v in valores if v is not None], dtype=float)
    if len(x) < 2 or x.mean() == 0:
        return None
    return float(x.std(ddof=1) / abs(x.mean()))
