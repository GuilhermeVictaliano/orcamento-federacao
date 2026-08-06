"""Estudos econômicos aplicados aos dados do painel.

Cada estudo devolve um dicionário com a mesma estrutura, para que a página apenas
renderize (sem lógica analítica na camada de UI):

    {
      "titulo", "hipotese", "metodo", "formula_latex", "referencia",
      "estatisticas": DataFrame ou dict, "veredito", "interpretacao",
      "ressalvas": [str], "severidade"
    }

Princípios: hipótese antes do número; fórmula visível; significância quando cabe;
resultado negativo também é resultado; limitações declaradas.

ATENÇÃO METODOLÓGICA: a amostra é pequena (7 entes, ~10 exercícios). Os resultados
são **exploratórios/descritivos da amostra**, não inferência sobre a população de
entes brasileiros, e as associações medidas **não implicam causalidade**.
"""

from __future__ import annotations

import pandas as pd

from analise.econometria import (
    coef_variacao,
    correlacao_defasada,
    gini,
    hhi,
    ols_simples,
    t_contra,
    teste_permutacao,
)

# Anos de eleição por nível (posse no ano seguinte).
ELEICOES_MUNICIPAIS = {2008, 2012, 2016, 2020, 2024, 2028}
ELEICOES_GERAIS = {2010, 2014, 2018, 2022, 2026}

FUNCOES_RIGIDAS = ["Previdência Social", "Encargos Especiais"]


def _fmt_pct(v, casas=1):
    return "—" if v is None else f"{v:.{casas}%}"


# ---------------------------------------------------------------------------
# Estudo 1 — Sustentabilidade fiscal (elasticidade despesa-receita)
# ---------------------------------------------------------------------------
def estudo_sustentabilidade(despesa_por_ente: dict, receita_por_ente: dict) -> dict:
    """Elasticidade da despesa em relação à receita, via OLS log-log.

    ln(D) = α + β·ln(R). β é a elasticidade: β>1 ⇒ a cada 1% de receita a mais, a
    despesa cresce mais de 1% — trajetória que, mantida, é insustentável. β≈1 ⇒
    despesa acompanha a receita. β<1 ⇒ postura fiscal conservadora.
    """
    import numpy as np

    linhas = []
    for ente, serie_d in despesa_por_ente.items():
        serie_r = receita_por_ente.get(ente, {})
        anos = sorted(set(serie_d) & set(serie_r))
        anos = [a for a in anos if serie_d.get(a, 0) > 0 and serie_r.get(a, 0) > 0]
        if len(anos) < 5:
            continue
        x = np.log([serie_r[a] for a in anos])
        y = np.log([serie_d[a] for a in anos])
        r = ols_simples(x, y)
        if not r:
            continue
        t = t_contra(r["beta"], r["se_beta"], 1.0)
        linhas.append({
            "Ente": ente,
            "β (elasticidade)": round(r["beta"], 3),
            "EP(β)": round(r["se_beta"], 3) if r["se_beta"] is not None else None,
            "t (H₀: β=1)": round(t, 2) if t is not None else None,
            "R²": round(r["r2"], 3) if r["r2"] is not None else None,
            "n (anos)": r["n"],
            "Leitura": ("despesa cresce mais que receita" if r["beta"] > 1.05
                        else ("conservador" if r["beta"] < 0.95 else "acompanha a receita")),
        })

    df = pd.DataFrame(linhas).sort_values("β (elasticidade)", ascending=False) if linhas else pd.DataFrame()
    acima = df[df["β (elasticidade)"] > 1.05]["Ente"].tolist() if not df.empty else []
    if acima:
        veredito = f"{len(acima)} ente(s) com elasticidade > 1: **{', '.join(acima)}**."
        sev = "atencao"
    else:
        veredito = "Nenhum ente apresenta elasticidade despesa-receita significativamente acima de 1."
        sev = "positivo"

    return {
        "titulo": "1. Sustentabilidade fiscal — a despesa cresce mais rápido que a receita?",
        "hipotese": "H₀: a elasticidade da despesa em relação à receita é 1 (despesa acompanha a receita). "
                    "H₁: β ≠ 1 — β > 1 indica trajetória de gasto acima da capacidade de arrecadação.",
        "metodo": "Regressão log-log por mínimos quadrados ordinários (OLS) sobre a série anual de "
                  "despesa liquidada e receita realizada de cada ente. O coeficiente β é lido "
                  "diretamente como elasticidade. Testa-se β=1 pela estatística t (regra prática |t|>2).",
        "formula_latex": r"\ln(D_t) = \alpha + \beta \ln(R_t) + \varepsilon_t "
                         r"\qquad \beta = \frac{\partial \ln D}{\partial \ln R}",
        "referencia": "Bohn (1998), *The Behavior of U.S. Public Debt and Deficits*; "
                      "Hakkio & Rush (1991), *Is the budget deficit too large?*",
        "estatisticas": df,
        "veredito": veredito,
        "interpretacao": "β mede quanto a despesa responde à receita. Valores acima de 1 sinalizam que o "
                         "ente amplia gastos além do que arrecada — sustentável no curto prazo via dívida "
                         "ou transferências, mas não indefinidamente. R² alto indica que a receita explica "
                         "bem a trajetória da despesa.",
        "ressalvas": [
            "Série curta (~10 pontos): o correto para sustentabilidade seria testar cointegração "
            "(Engle-Granger/Johansen), o que exige séries longas. Este OLS é **exploratório**.",
            "Valores nominais em log; a inflação afeta ambos os lados e tende a se cancelar na elasticidade, "
            "mas não elimina o viés de períodos de inflação muito volátil.",
            "Associação, não causalidade.",
        ],
        "severidade": sev,
    }


# ---------------------------------------------------------------------------
# Estudo 2 — Ciclo político-orçamentário
# ---------------------------------------------------------------------------
def estudo_ciclo_politico(crescimento_real_por_ente: dict, nivel_por_ente: dict, n_perm: int = 5000) -> dict:
    """Testa se o crescimento real da despesa é maior em anos eleitorais.

    Teoria do ciclo político-orçamentário: incumbentes expandem gastos às vésperas
    da eleição para sinalizar competência ao eleitorado.
    """
    grupo_eleicao, grupo_normal = [], []
    linhas = []
    for ente, serie in crescimento_real_por_ente.items():
        nivel = nivel_por_ente.get(ente, "federal")
        anos_eleitorais = ELEICOES_MUNICIPAIS if nivel == "municipal" else ELEICOES_GERAIS
        el = [g for a, g in serie.items() if a in anos_eleitorais]
        nao = [g for a, g in serie.items() if a not in anos_eleitorais]
        grupo_eleicao += el
        grupo_normal += nao
        if el and nao:
            m_el = sum(el) / len(el)
            m_nao = sum(nao) / len(nao)
            linhas.append({
                "Ente": ente,
                "Nível": nivel,
                "Cresc. real médio — ano eleitoral": _fmt_pct(m_el),
                "Cresc. real médio — demais anos": _fmt_pct(m_nao),
                "Diferença (p.p.)": round(100 * (m_el - m_nao), 1),
                "n eleitoral": len(el),
            })

    teste = teste_permutacao(grupo_eleicao, grupo_normal, n_perm=n_perm) if grupo_eleicao and grupo_normal else {}
    df = pd.DataFrame(linhas) if linhas else pd.DataFrame()

    if teste:
        p = teste["p_valor"]
        dif_pp = 100 * teste["diferenca"]
        significativo = p < 0.05
        if significativo:
            veredito = (f"Diferença de **{dif_pp:+.1f} p.p.** em anos eleitorais, "
                        f"**estatisticamente significativa** (p = {p:.3f} < 0,05). H₀ rejeitada.")
            sev = "alerta"
        else:
            veredito = (f"Diferença observada de {dif_pp:+.1f} p.p., mas **sem significância estatística** "
                        f"(p = {p:.3f} ≥ 0,05). **Não há evidência** de ciclo político-orçamentário nesta amostra.")
            sev = "info"
    else:
        veredito = "Dados insuficientes para o teste."
        sev = "info"

    return {
        "titulo": "2. Ciclo político-orçamentário — o gasto sobe em ano de eleição?",
        "hipotese": "H₀: o crescimento real da despesa tem a mesma média em anos eleitorais e não eleitorais. "
                    "H₁: a média difere (a teoria prevê expansão pré-eleitoral).",
        "metodo": "Classificam-se os anos por nível (eleições municipais 2016/2020/2024; gerais 2018/2022/2026) "
                  "e compara-se o crescimento real (deflacionado pelo IPCA) dos dois grupos por **teste de "
                  "permutação** com reamostragem — não-paramétrico, adequado a amostras pequenas, sem supor "
                  "normalidade. Semente fixa garante reprodutibilidade.",
        "formula_latex": r"p = \frac{1 + \#\{|\bar{x}^{*}_{e} - \bar{x}^{*}_{n}| \ge "
                         r"|\bar{x}_{e} - \bar{x}_{n}|\}}{1 + B}",
        "referencia": "Nordhaus (1975), *The Political Business Cycle*; Rogoff & Sibert (1988), "
                      "*Elections and Macroeconomic Policy Cycles*; Brender & Drazen (2005); "
                      "Sakurai & Menezes-Filho (2008) para o caso brasileiro.",
        "estatisticas": df,
        "teste": teste,
        "veredito": veredito,
        "interpretacao": "Um p-valor alto **não prova ausência** de ciclo — indica que, com esta amostra, a "
                         "diferença observada é compatível com variação aleatória. Note que efeitos agregados "
                         "podem ser dominados por choques idiossincráticos (ex.: 2020–2022, pandemia).",
        "ressalvas": [
            "Poucos anos eleitorais por ente (2 a 3) — baixo poder estatístico.",
            "Choques exógenos (pandemia, refinanciamento da dívida federal) coincidem com anos eleitorais e "
            "contaminam a comparação.",
            "O desenho não controla covariáveis (ciclo econômico, transferências); um teste rigoroso exigiria "
            "painel com efeitos fixos de ente e ano.",
        ],
        "severidade": sev,
    }


# ---------------------------------------------------------------------------
# Estudo 3 — Rigidez orçamentária
# ---------------------------------------------------------------------------
def estudo_rigidez(tabela_despesa: pd.DataFrame) -> dict:
    """Parcela do orçamento comprometida com despesas de baixa discricionariedade."""
    linhas = []
    if not tabela_despesa.empty:
        for ente, sub in tabela_despesa.groupby("ente"):
            total = sub["realizado"].sum()
            if not total:
                continue
            rigida = sub[sub["funcao"].isin(FUNCOES_RIGIDAS)]["realizado"].sum()
            r = rigida / total
            linhas.append({
                "Ente": ente,
                "Rigidez": _fmt_pct(r),
                "Espaço fiscal": _fmt_pct(1 - r),
                "_rigidez": r,
            })
    df = pd.DataFrame(linhas).sort_values("_rigidez", ascending=False) if linhas else pd.DataFrame()
    if not df.empty:
        pior = df.iloc[0]
        veredito = (f"Maior rigidez: **{pior['Ente']}** com {pior['Rigidez']} do orçamento comprometido — "
                    f"resta {pior['Espaço fiscal']} de espaço fiscal discricionário.")
        sev = "atencao" if pior["_rigidez"] >= 0.5 else "info"
        df = df.drop(columns=["_rigidez"])
    else:
        veredito, sev = "Sem dados.", "info"

    return {
        "titulo": "3. Rigidez orçamentária — quanto do orçamento é intocável?",
        "hipotese": "Mensuração (não é teste de hipótese): qual fração da despesa está comprometida com "
                    "obrigações de baixa discricionariedade no curto prazo.",
        "metodo": "Razão entre a despesa nas funções de baixa discricionariedade (Previdência Social e "
                  "Encargos Especiais — juros, amortização e sentenças) e a despesa total liquidada. "
                  "O complemento é o espaço fiscal disponível para políticas novas.",
        "formula_latex": r"\text{Rigidez} = \frac{D_{\text{Previdência}} + D_{\text{Encargos}}}{D_{\text{total}}}"
                         r"\qquad \text{Espaço fiscal} = 1 - \text{Rigidez}",
        "referencia": "Conceito consolidado na literatura fiscal brasileira (Instituição Fiscal Independente; "
                      "Tesouro Nacional — despesas obrigatórias vs discricionárias).",
        "estatisticas": df,
        "veredito": veredito,
        "interpretacao": "Rigidez alta significa que, mesmo com receita crescente, o gestor tem pouca margem "
                         "para redirecionar recursos: o orçamento já 'chega comprometido'. É o principal limite "
                         "prático à execução de novas políticas públicas.",
        "ressalvas": [
            "Proxy por função de governo; a classificação legal de obrigatoriedade (pessoal, vinculações "
            "constitucionais) é mais ampla e não é separável no RREO-Anexo 02.",
            "Encargos Especiais da União incluem refinanciamento da dívida, o que infla a rigidez federal "
            "frente à de municípios.",
        ],
        "severidade": sev,
    }


# ---------------------------------------------------------------------------
# Estudo 4 — Concentração de receita (HHI)
# ---------------------------------------------------------------------------
def estudo_concentracao_receita(tabela_receita: pd.DataFrame) -> dict:
    """Diversificação das fontes de receita medida pelo índice Herfindahl-Hirschman."""
    linhas = []
    if not tabela_receita.empty:
        for ente, sub in tabela_receita.groupby("ente"):
            s = sub.groupby("categoria")["realizada"].sum()
            r = hhi(s.values)
            if not r:
                continue
            linhas.append({
                "Ente": ente,
                "HHI": round(r["hhi"], 3),
                "Concentração": r["faixa"],
                "Equivalente a N fontes iguais": round(r["equivalente_partes_iguais"], 1),
                "Fontes com receita": r["n_partes"],
            })
    df = pd.DataFrame(linhas).sort_values("HHI", ascending=False) if linhas else pd.DataFrame()
    if not df.empty:
        pior = df.iloc[0]
        veredito = (f"**{pior['Ente']}** tem a receita mais concentrada (HHI = {pior['HHI']}, "
                    f"equivalente a apenas {pior['Equivalente a N fontes iguais']} fontes iguais).")
        sev = "atencao" if pior["HHI"] > 0.25 else "info"
    else:
        veredito, sev = "Sem dados.", "info"

    return {
        "titulo": "4. Concentração da receita — vulnerabilidade por falta de diversificação",
        "hipotese": "Mensuração: quão dependente cada ente é de poucas fontes de receita. "
                    "Maior concentração ⇒ maior exposição a choques numa única base tributária.",
        "metodo": "Índice Herfindahl-Hirschman sobre as participações das categorias econômicas de receita. "
                  "Faixas (escala 0–1, equivalentes às do DOJ/FTC): <0,15 baixa; 0,15–0,25 moderada; >0,25 alta. "
                  "O inverso do HHI é o 'número equivalente de fontes iguais'.",
        "formula_latex": r"HHI = \sum_{i=1}^{N} s_i^2, \quad s_i = \frac{R_i}{\sum_j R_j}"
                         r"\qquad N_{\text{eq}} = 1/HHI",
        "referencia": "Hirschman (1945); Herfindahl (1950). Faixas de interpretação: U.S. DOJ/FTC "
                      "*Horizontal Merger Guidelines*.",
        "estatisticas": df,
        "veredito": veredito,
        "interpretacao": "O HHI é o padrão para medir concentração. Aqui ele mede risco de receita: um ente "
                         "cuja arrecadação depende de poucas fontes (ex.: um estado fortemente dependente do "
                         "ICMS) sofre mais com uma retração setorial do que um ente com base diversificada.",
        "ressalvas": [
            "Categorias econômicas do RREO-Anexo 01, não tributos individuais — a concentração real dentro de "
            "'Impostos' (ex.: peso do ICMS) não é observável nesta fonte.",
            "Transferências constitucionais aparecem como categoria única, o que pode subestimar a "
            "diversificação de origem dos recursos.",
        ],
        "severidade": sev,
    }


# ---------------------------------------------------------------------------
# Estudo 5 — Desigualdade do gasto per capita (Gini)
# ---------------------------------------------------------------------------
def estudo_desigualdade_per_capita(despesa_por_ente_ano: dict, populacoes: dict, ano: int) -> dict:
    """Gini da despesa per capita entre os entes subnacionais comparáveis."""
    pares = []
    for ente, pop in populacoes.items():
        valor = despesa_por_ente_ano.get(ente, {}).get(ano)
        if pop and valor:
            pares.append((ente, valor / pop))
    pares.sort(key=lambda p: p[1], reverse=True)
    g = gini([v for _, v in pares]) if len(pares) >= 2 else None

    df = pd.DataFrame(
        [{"Ente": e, "Despesa per capita (R$)": round(v, 2)} for e, v in pares]
    ) if pares else pd.DataFrame()

    if g is not None:
        maior = f"{pares[0][1]:,.0f}".replace(",", ".")
        menor = f"{pares[-1][1]:,.0f}".replace(",", ".")
        razao = pares[0][1] / pares[-1][1] if pares[-1][1] else float("inf")
        veredito = (f"Gini = **{g:.3f}** entre {len(pares)} entes. "
                    f"Extremos: {pares[0][0]} (R$ {maior}/hab) e {pares[-1][0]} (R$ {menor}/hab), "
                    f"razão de {razao:.1f}x.")
        sev = "atencao" if g > 0.2 else "info"
    else:
        veredito, sev = "Dados insuficientes.", "info"

    return {
        "titulo": "5. Desigualdade do gasto per capita entre entes",
        "hipotese": "Mensuração: quão desigual é a despesa por habitante entre os entes subnacionais "
                    "comparáveis — proxy da desigualdade de capacidade de prover serviços.",
        "metodo": "Coeficiente de Gini sobre a despesa liquidada por habitante. A União é excluída porque o "
                  "campo de população do RREO federal é inconsistente na fonte.",
        "formula_latex": r"G = \frac{\sum_{i}\sum_{j} |x_i - x_j|}{2n^2\bar{x}}",
        "referencia": "Gini (1912), *Variabilità e mutabilità*.",
        "estatisticas": df,
        "veredito": veredito,
        "interpretacao": "Gini 0 seria gasto por habitante idêntico entre os entes; quanto maior, mais "
                         "desigual. Diferenças refletem base econômica (ex.: cidades portuárias/industriais "
                         "arrecadam mais), atribuições distintas e capacidade fiscal.",
        "ressalvas": [
            "Amostra pequena e não aleatória (entes escolhidos por conveniência, todos de SP) — não "
            "generalizável para o Brasil.",
            "Não ajusta por diferenças de competências entre estado e municípios, nem por custo de vida.",
        ],
        "severidade": sev,
    }


# ---------------------------------------------------------------------------
# Estudo 6 — Pass-through juros → serviço da dívida
# ---------------------------------------------------------------------------
def estudo_passthrough_juros(selic_por_ano: dict, peso_encargos_por_ano: dict, max_lag: int = 2) -> dict:
    """Associação entre a Selic e o peso dos Encargos Especiais na despesa federal."""
    anos = sorted(set(selic_por_ano) & set(peso_encargos_por_ano))
    x = [selic_por_ano[a] for a in anos]
    y = [peso_encargos_por_ano[a] for a in anos]
    resultado = correlacao_defasada(x, y, max_lag=max_lag) if len(anos) >= 4 else {}

    df = pd.DataFrame([
        {"Ano": a, "Selic média (% a.a.)": round(selic_por_ano[a], 2),
         "Encargos / despesa total": _fmt_pct(peso_encargos_por_ano[a])}
        for a in anos
    ]) if anos else pd.DataFrame()

    if resultado:
        rho = resultado["melhor_rho"]
        lag = resultado["melhor_lag"]
        forca = "forte" if abs(rho) >= 0.7 else ("moderada" if abs(rho) >= 0.4 else "fraca")
        veredito = f"Correlação **{forca}** (ρ = {rho:+.2f}) na defasagem de {lag} ano(s), com n = {len(anos)}. "
        if abs(rho) < 0.4:
            veredito += ("A hipótese de que juros altos pressionam o orçamento **não encontra suporte** "
                         "nesta amostra.")
        elif rho < 0:
            # Sinal oposto ao previsto pela teoria — merece destaque, não pode passar batido.
            veredito += ("⚠️ O sinal é **negativo**, isto é, **contrário** ao que a teoria prevê "
                         "(juros maiores associados a *menor* peso dos encargos). Isso sugere que o "
                         "resultado é dominado por outros fatores — provavelmente o denominador "
                         "(despesa total) e o refinanciamento da dívida — e **não** deve ser lido como "
                         "efeito causal dos juros.")
        else:
            veredito += "O sinal é positivo, na direção prevista pela teoria."
        sev = "info" if abs(rho) < 0.4 else "atencao"
    else:
        veredito, sev = "Série insuficiente para estimar a correlação.", "info"

    return {
        "titulo": "6. Pass-through de juros — a Selic pressiona o serviço da dívida?",
        "hipotese": "H₀: não há associação linear entre a Selic média do ano e a parcela da despesa federal "
                    "destinada a Encargos Especiais. H₁: há associação, possivelmente defasada.",
        "metodo": "Correlação de Pearson entre a Selic média anual (BCB/SGS série 432) e o peso dos Encargos "
                  "Especiais na despesa federal, testada em defasagens de 0 a 2 anos — o repasse de juros ao "
                  "serviço da dívida não é instantâneo (perfil de vencimentos e indexação).",
        "formula_latex": r"\rho_k = \frac{\text{cov}(\text{Selic}_t,\ \text{Encargos}_{t+k})}"
                         r"{\sigma_{\text{Selic}}\ \sigma_{\text{Encargos}}}, \quad k = 0,1,2",
        "referencia": "Macroeconomia fiscal padrão (relação juros–serviço da dívida); dados: Banco Central "
                      "do Brasil, Sistema Gerenciador de Séries Temporais.",
        "estatisticas": df,
        "correlacao": resultado,
        "veredito": veredito,
        "interpretacao": "Uma correlação fraca não significa que juros não importam: o peso dos Encargos é "
                         "afetado simultaneamente pelo estoque e perfil da dívida, pelo refinanciamento e pelo "
                         "denominador (despesa total). É um alerta contra leituras causais simplistas.",
        "ressalvas": [
            "n ≈ 10 observações anuais: correlações são muito instáveis nesse tamanho.",
            "O peso dos Encargos tem no denominador a despesa total, que varia por razões alheias aos juros.",
            "Correlação não é causalidade; não há controle para dívida/PIB, câmbio ou composição da dívida.",
        ],
        "severidade": sev,
    }
