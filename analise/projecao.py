"""Motor de projeção — "imaginar o futuro com os dados de hoje", com método explícito.

Duas técnicas, ambas simples e explicáveis ao cidadão (nada de caixa-preta):

1. **Anualização por sazonalidade** — o RREO é acumulado; até um dado bimestre
   executa-se uma fração historicamente estável do ano. Projeção do fechamento =
   realizado_parcial / fração_histórica. A faixa vem do mínimo/máximo histórico.

2. **Tendência linear** — regressão simples sobre a série anual para o cenário
   "se mantiver o ritmo".

Tudo aqui é função pura e testável. Projeção NÃO é fato — quem usa vê o método,
a faixa e o erro histórico (back-test).
"""

from __future__ import annotations


def fracao_executada(parciais: dict[int, float], fechados: dict[int, float]) -> dict:
    """Fração do ano executada até o bimestre parcial, por ano histórico.

    parciais/fechados: {ano: realizado_ate_o_bimestre} e {ano: realizado_ano_fechado}.
    Retorna {fracoes: {ano: frac}, media, minimo, maximo}.
    """
    fracoes = {
        ano: parciais[ano] / fechados[ano]
        for ano in parciais
        if ano in fechados and fechados[ano]
    }
    if not fracoes:
        return {"fracoes": {}, "media": None, "minimo": None, "maximo": None}
    valores = list(fracoes.values())
    return {
        "fracoes": fracoes,
        "media": sum(valores) / len(valores),
        "minimo": min(valores),
        "maximo": max(valores),
    }


def projetar_ano(realizado_parcial: float, saz: dict) -> dict:
    """Projeta o fechamento do ano a partir do realizado parcial e da sazonalidade.

    saz = saída de `fracao_executada`. Retorna {projecao, minimo, maximo} — a faixa
    reflete quão cedo/tarde o ano costuma executar. Vazio se não houver base.
    """
    media, mn, mx = saz.get("media"), saz.get("minimo"), saz.get("maximo")
    if not media or realizado_parcial is None:
        return {}
    return {
        "projecao": realizado_parcial / media,
        # fração maior no histórico ⇒ ano fecha proporcionalmente menor, e vice-versa.
        "minimo": realizado_parcial / mx if mx else None,
        "maximo": realizado_parcial / mn if mn else None,
    }


def erro_backtest(parciais: dict[int, float], fechados: dict[int, float]) -> float | None:
    """Erro médio do método de anualização, testado nos anos fechados (leave-one-out).

    Para cada ano, projeta usando a fração média dos OUTROS anos e compara ao real.
    Retorna o erro percentual absoluto médio (ex.: 0.08 = 8%). None se base insuficiente.
    """
    anos = [a for a in parciais if a in fechados and fechados[a]]
    if len(anos) < 2:
        return None
    erros = []
    for alvo in anos:
        outros = [a for a in anos if a != alvo]
        fracs = [parciais[a] / fechados[a] for a in outros]
        frac_media = sum(fracs) / len(fracs)
        if not frac_media:
            continue
        projetado = parciais[alvo] / frac_media
        erros.append(abs(projetado - fechados[alvo]) / fechados[alvo])
    return sum(erros) / len(erros) if erros else None


def tendencia_linear(serie: dict[int, float]) -> dict:
    """Regressão linear simples sobre {ano: valor}. Projeta o próximo ano.

    Retorna {inclinacao, intercepto, projecao_proximo_ano, proximo_ano}. Vazio se <2 pontos.
    """
    pontos = sorted((a, v) for a, v in serie.items() if v is not None)
    n = len(pontos)
    if n < 2:
        return {}
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if not denom:
        return {}
    inclinacao = sum((x - mx) * (y - my) for x, y in pontos) / denom
    intercepto = my - inclinacao * mx
    proximo = xs[-1] + 1
    return {
        "inclinacao": inclinacao,
        "intercepto": intercepto,
        "proximo_ano": proximo,
        "projecao_proximo_ano": inclinacao * proximo + intercepto,
    }


def crescimento_vs_inflacao(serie_nominal: dict[int, float], fatores_ipca: dict[int, float]) -> list[dict]:
    """Crescimento nominal e REAL ano a ano de uma série.

    fatores_ipca: {ano: fator_para_o_ano_base} (de extract.inflacao.fatores_para_base).
    Retorna lista {ano, nominal, real} ordenada por ano (a partir do 2º ano).
    """
    anos = sorted(a for a, v in serie_nominal.items() if v is not None)
    resultado = []
    for i in range(1, len(anos)):
        ant, atual = anos[i - 1], anos[i]
        v_ant, v_atual = serie_nominal[ant], serie_nominal[atual]
        if not v_ant:
            continue
        nominal = v_atual / v_ant - 1
        fa, fb = fatores_ipca.get(ant), fatores_ipca.get(atual)
        real = ((v_atual * fb) / (v_ant * fa) - 1) if fa and fb else None
        resultado.append({"ano": atual, "nominal": nominal, "real": real})
    return resultado
