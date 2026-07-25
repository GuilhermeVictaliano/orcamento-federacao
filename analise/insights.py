"""Motor de insights — funções puras que viram os "destaques do guardião".

Recebe os dados que as páginas já carregam (despesa por função, receita por
categoria, populações) e devolve achados em linguagem natural com severidade,
prontos para exibir. Sem dependência de Streamlit — testável isoladamente.

Ressalva importante: a população da UNIÃO vem incorreta no SICONFI, então
qualquer métrica per capita ignora a União (ver `populacoes_validas`).
"""

import pandas as pd

from transform.fiscal import FUNCAO_ENCARGOS, FUNCAO_PREVIDENCIA, peso_por_funcao
from transform.receita import totais_receita_por_ente

ENTE_SEM_POPULACAO_CONFIAVEL = "União"

# Limiares de dependência de transferências (fatia da receita vinda de repasses).
LIMITE_DEP_ALTA = 0.50
LIMITE_DEP_MEDIA = 0.30

# Mínimos constitucionais (contexto educativo; base legal é a receita, não a despesa total).
MINIMO_SAUDE = 0.15       # EC 29/2000 — 15% da receita de impostos e transferências
MINIMO_EDUCACAO = 0.25    # Art. 212 CF — 25%


def populacoes_validas(pop_por_ente: dict) -> dict:
    """Mantém só entes com população confiável (>0 e diferente da União)."""
    return {
        ente: int(pop)
        for ente, pop in pop_por_ente.items()
        if pop and pop > 0 and ente != ENTE_SEM_POPULACAO_CONFIAVEL
    }


def per_capita(valores_por_ente: dict, populacoes: dict) -> dict:
    """Valor por habitante para os entes com população válida."""
    return {
        ente: valores_por_ente[ente] / populacoes[ente]
        for ente in valores_por_ente
        if ente in populacoes and populacoes[ente]
    }


def dependencia_transferencias(tabela_receita: pd.DataFrame) -> pd.DataFrame:
    """% da receita de cada ente vinda de transferências vs arrecadação própria.

    Retorna: ente, total, transferencias, tributaria, pct_transferencias, pct_tributaria.
    """
    colunas = ["ente", "total", "transferencias", "tributaria", "pct_transferencias", "pct_tributaria"]
    if tabela_receita.empty:
        return pd.DataFrame(columns=colunas)

    linhas = []
    for ente, sub in tabela_receita.groupby("ente"):
        total = sub["realizada"].sum()
        transf = sub[sub["categoria"].str.contains("Transfer", case=False, na=False)]["realizada"].sum()
        trib = sub[sub["categoria"].str.contains("Tribut", case=False, na=False)]["realizada"].sum()
        linhas.append(
            {
                "ente": ente,
                "total": total,
                "transferencias": transf,
                "tributaria": trib,
                "pct_transferencias": (transf / total) if total else None,
                "pct_tributaria": (trib / total) if total else None,
            }
        )
    return pd.DataFrame(linhas, columns=colunas)


def classificar_dependencia(pct) -> dict:
    """Semáforo da dependência de transferências (quanto maior, mais vulnerável)."""
    if pct is None or pd.isna(pct):
        return {"icone": "⚪", "rotulo": "Sem dado", "severidade": "info"}
    if pct >= LIMITE_DEP_ALTA:
        return {"icone": "🔴", "rotulo": "Alta dependência", "severidade": "alerta"}
    if pct >= LIMITE_DEP_MEDIA:
        return {"icone": "🟡", "rotulo": "Dependência média", "severidade": "atencao"}
    return {"icone": "🟢", "rotulo": "Autonomia alta", "severidade": "positivo"}


def variacao_real(
    despesa_por_funcao_ini: dict, despesa_por_funcao_fim: dict,
    fator_ini: float, fator_fim: float, valor_minimo: float = 1e9,
) -> list[dict]:
    """Variação REAL (deflacionada) por função entre dois anos, ordenada.

    Recebe dicts {funcao: valor_nominal} e os fatores de deflação de cada ano.
    Ignora funções cujo valor inicial real seja menor que `valor_minimo` (ruído).
    """
    resultado = []
    for funcao, v_ini in despesa_por_funcao_ini.items():
        v_fim = despesa_por_funcao_fim.get(funcao)
        if v_fim is None:
            continue
        real_ini = v_ini * fator_ini
        real_fim = v_fim * fator_fim
        if real_ini < valor_minimo:
            continue
        resultado.append(
            {"funcao": funcao, "variacao": (real_fim / real_ini - 1), "real_fim": real_fim}
        )
    return sorted(resultado, key=lambda d: d["variacao"], reverse=True)


def _fmt_reais(v) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def _fmt_pct(v) -> str:
    return f"{v:.0%}"


def _fmt_milhoes(v) -> str:
    if v >= 1e9:
        return f"R$ {v/1e9:,.1f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {v/1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")


def concentracao_fornecedores(tabela_contratos: pd.DataFrame) -> dict:
    """Concentração do valor contratado por fornecedor — sinal de favorecimento/dependência.

    Retorna total, nº de contratos e fornecedores, fornecedor líder e sua fatia,
    e a fatia dos 5 maiores. Dict vazio se não houver dados.
    """
    if tabela_contratos.empty or "valor_global" not in tabela_contratos.columns:
        return {}
    df = tabela_contratos.dropna(subset=["valor_global"])
    total = df["valor_global"].sum()
    if not total:
        return {}
    por_forn = df.groupby("fornecedor")["valor_global"].sum().sort_values(ascending=False)
    return {
        "total": float(total),
        "n_contratos": int(len(df)),
        "n_fornecedores": int(len(por_forn)),
        "top_fornecedor": str(por_forn.index[0]),
        "top_valor": float(por_forn.iloc[0]),
        "top_share": float(por_forn.iloc[0] / total),
        "top5_share": float(por_forn.head(5).sum() / total),
    }


def destaques_contratos(tabela_contratos: pd.DataFrame) -> list[dict]:
    """Achados de guardião sobre um conjunto de contratos (concentração e vultosos)."""
    achados = []
    c = concentracao_fornecedores(tabela_contratos)
    if not c:
        return achados

    # 1. Concentração no maior fornecedor.
    share = c["top_share"]
    sev = "alerta" if share >= 0.30 else ("atencao" if share >= 0.15 else "info")
    achados.append({
        "icone": "🏗️" if sev == "info" else "⚠️",
        "titulo": "Concentração de fornecedor",
        "texto": f"O fornecedor **{c['top_fornecedor']}** concentra **{_fmt_pct(share)}** do valor "
                 f"contratado ({_fmt_milhoes(c['top_valor'])}), entre {c['n_fornecedores']} fornecedores. "
                 f"Concentração alta merece um olhar mais atento.",
        "severidade": sev,
    })

    # 2. Regra de Pareto: poucos contratos concentram a maior parte do valor.
    df = tabela_contratos.dropna(subset=["valor_global"]).sort_values("valor_global", ascending=False)
    total = df["valor_global"].sum()
    if total:
        acum = df["valor_global"].cumsum() / total
        n_ate_80 = int((acum < 0.80).sum()) + 1
        pct_contratos = n_ate_80 / len(df)
        achados.append({
            "icone": "📊",
            "titulo": "Regra 80/20",
            "texto": f"**{n_ate_80}** contratos (só {_fmt_pct(pct_contratos)} do total de {c['n_contratos']}) "
                     f"concentram **80%** de todo o valor. São eles que merecem prioridade na auditoria.",
            "severidade": "info",
        })
    return achados


def destaques_poderes(tabela_restos: pd.DataFrame) -> list[dict]:
    """Achado sobre o estoque de restos a pagar (contas de anos anteriores não quitadas)."""
    achados = []
    if tabela_restos.empty or "restos_a_pagar" not in tabela_restos.columns:
        return achados
    por_ente = tabela_restos.groupby("ente")["restos_a_pagar"].sum().sort_values(ascending=False)
    if por_ente.empty or not por_ente.iloc[0]:
        return achados
    ente = por_ente.index[0]
    valor = por_ente.iloc[0]
    achados.append({
        "icone": "🧾",
        "titulo": "Herança de contas a pagar",
        "texto": f"**{ente}** carrega o maior estoque de restos a pagar: **{_fmt_milhoes(valor)}** em "
                 f"obrigações de anos anteriores ainda não quitadas.",
        "severidade": "atencao",
    })
    return achados


def destaques_periodo(serie_ente: pd.DataFrame, metrica_label: str, ente: str) -> list[dict]:
    """Achados sobre a trajetória de um ente por mandato.

    `serie_ente` precisa ter colunas: ano, mandato, valor (já deflacionada se real).
    Compara a média por mandato (variação entre o primeiro e o último mandato com dado).
    """
    achados = []
    if serie_ente.empty or "mandato" not in serie_ente.columns:
        return achados
    validos = serie_ente[serie_ente["mandato"] != "—"]
    medias = validos.groupby("mandato")["valor"].mean()
    if len(medias) < 2:
        return achados
    mandatos = list(medias.index)
    primeiro, ultimo = medias.iloc[0], medias.iloc[-1]
    if not primeiro:
        return achados
    var = ultimo / primeiro - 1
    direcao = "cresceu" if var >= 0 else "caiu"
    sev = "atencao" if abs(var) >= 0.20 else "info"
    achados.append({
        "icone": "📈" if var >= 0 else "📉",
        "titulo": f"{metrica_label} entre mandatos",
        "texto": f"Em **{ente}**, a média anual {direcao} **{_fmt_pct(abs(var))}** do mandato "
                 f"{mandatos[0]} para o {mandatos[-1]}.",
        "severidade": sev,
    })
    return achados


def destaques(tabela_despesa: pd.DataFrame, tabela_receita: pd.DataFrame, pop_por_ente: dict) -> list[dict]:
    """Gera os destaques do guardião (lista de {icone, titulo, texto, severidade}).

    Cada destaque é uma frase pronta em linguagem simples, computada ao vivo.
    """
    achados = []
    pops = populacoes_validas(pop_por_ente)

    # 1. Despesa per capita: quem mais e quem menos gasta por habitante.
    if not tabela_despesa.empty and pops:
        total_ente = tabela_despesa.groupby("ente")["realizado"].sum().to_dict()
        pc = per_capita(total_ente, pops)
        if len(pc) >= 2:
            maior = max(pc, key=pc.get)
            menor = min(pc, key=pc.get)
            achados.append({
                "icone": "👤",
                "titulo": "Gasto por habitante",
                "texto": f"**{maior}** gasta **{_fmt_reais(pc[maior])}/hab**, o maior entre os entes com "
                         f"população comparável — contra **{_fmt_reais(pc[menor])}/hab** de **{menor}**, o menor.",
                "severidade": "info",
            })

    # 2. Dependência de transferências: o mais vulnerável.
    dep = dependencia_transferencias(tabela_receita)
    if not dep.empty:
        dep_ok = dep[dep["pct_transferencias"].notna()].sort_values("pct_transferencias", ascending=False)
        if not dep_ok.empty:
            top = dep_ok.iloc[0]
            cls = classificar_dependencia(top["pct_transferencias"])
            achados.append({
                "icone": cls["icone"],
                "titulo": "Vulnerabilidade fiscal",
                "texto": f"**{top['ente']}** depende de transferências para **{_fmt_pct(top['pct_transferencias'])}** "
                         f"da receita (arrecada só {_fmt_pct(top['pct_tributaria'])} sozinho) — "
                         f"quanto maior, mais refém de repasses de outros governos.",
                "severidade": cls["severidade"],
            })

    # 3. Peso da Previdência e dos Encargos (rigidez) — usa o maior peso observado.
    if not tabela_despesa.empty:
        prev = peso_por_funcao(tabela_despesa, FUNCAO_PREVIDENCIA)
        prev = prev[prev["peso"].notna()].sort_values("peso", ascending=False)
        if not prev.empty:
            linha = prev.iloc[0]
            achados.append({
                "icone": "🏛️",
                "titulo": "Peso da Previdência",
                "texto": f"Em **{linha['ente']}**, a Previdência Social consome **{_fmt_pct(linha['peso'])}** "
                         f"de toda a despesa — recurso comprometido que não financia serviços novos.",
                "severidade": "atencao" if linha["peso"] >= 0.25 else "info",
            })
        enc = peso_por_funcao(tabela_despesa, FUNCAO_ENCARGOS)
        enc = enc[enc["peso"].notna()].sort_values("peso", ascending=False)
        if not enc.empty:
            linha = enc.iloc[0]
            achados.append({
                "icone": "💸",
                "titulo": "Encargos e dívida",
                "texto": f"Em **{linha['ente']}**, os Encargos Especiais (juros/amortização da dívida e "
                         f"sentenças) somam **{_fmt_pct(linha['peso'])}** da despesa.",
                "severidade": "atencao" if linha["peso"] >= 0.30 else "info",
            })

    return achados
