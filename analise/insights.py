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
