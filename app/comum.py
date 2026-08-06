"""Helpers compartilhados entre as páginas do painel (home + app/pages/*).

Concentra formatação, carregamento cacheado de dados do SICONFI e enriquecimento
de percentuais, para que cada página não reimplemente o mesmo código.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app.cores import classificar_execucao
from extract.config import ANEXO_RECEITA, ANEXO_RESTOS_A_PAGAR, ENTES_MVP
from extract.rreo import baixar_rreo, data_atualizacao, ultimo_bimestre_publicado
from transform.normalizar import normalizar_varios
from transform.poderes import normalizar_restos_varios
from transform.receita import normalizar_receita_varios


def formatar_reais(valor) -> str:
    if pd.isna(valor):
        return "—"
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_pct(valor) -> str:
    if pd.isna(valor):
        return "—"
    return f"{valor:.1%}"


def botao_download_csv(df: pd.DataFrame, nome_arquivo: str, label: str = "⬇️ Baixar CSV") -> None:
    """Botão de download da tabela em CSV (utf-8-sig, separador ';' — abre bem no Excel BR)."""
    csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(label, data=csv, file_name=nome_arquivo, mime="text/csv")


def abertura(texto: str) -> None:
    """Abertura curta em linguagem simples ('o que você vê e por que importa')."""
    st.markdown(f"> 🛡️ {texto}")


def negrito_para_html(texto: str) -> str:
    """Converte **negrito** de markdown em <b> — necessário dentro de blocos HTML crus,
    onde o Streamlit não interpreta markdown."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto or "")


def seletor_ano_bimestre(anos: list[int], chave: str = "") -> tuple[int, int, int]:
    """Seletor padrão focado no ANO INTEIRO; o bimestre vira opção avançada.

    Retorna (exercicio, ultimo_bimestre, bimestre). Por padrão bimestre = último
    publicado (= ano completo p/ anos fechados). Um expander permite escolher um
    bimestre específico.
    """
    exercicio = st.selectbox("Exercício (ano completo)", options=anos, index=0, key=f"ano_{chave}")
    ultimo = bimestre_recente_uniao(exercicio)
    if ultimo < 6:
        st.caption(f"⏳ {exercicio} ainda não fechou — dados até o {ultimo}º bimestre (acumulado no ano).")
    bimestre = ultimo
    with st.expander("⚙️ Analisar por bimestre específico (avançado)"):
        bimestre = st.selectbox(
            "Bimestre (RREO)", options=list(range(1, ultimo + 1)), index=ultimo - 1, key=f"bim_{chave}",
            help="Cada bimestre traz o acumulado desde o início do ano.",
        )
    return exercicio, ultimo, bimestre


def composicao_help(df: pd.DataFrame, categoria_col: str, valor_col: str, n: int = 5, titulo: str = "Composição") -> str:
    """String 'Categoria X% · Categoria Y% · …' para usar como tooltip (help=) de um valor.

    Mostra as `n` maiores categorias e agrupa o restante em 'outros'.
    """
    if df.empty or categoria_col not in df or valor_col not in df:
        return ""
    agg = df.groupby(categoria_col)[valor_col].sum().sort_values(ascending=False)
    total = agg.sum()
    if not total:
        return ""
    partes = [f"{cat}: {(val / total):.0%}" for cat, val in agg.head(n).items()]
    resto = agg.iloc[n:].sum()
    if resto > 0:
        partes.append(f"outros: {(resto / total):.0%}")
    return f"{titulo} — " + " · ".join(partes)


# cor (hex RGB) por severidade; a ordem também define a prioridade de exibição.
_ESTILO_SEVERIDADE = {
    "alerta": (211, 59, 59),
    "atencao": (250, 178, 25),
    "positivo": (12, 163, 12),
    "info": (42, 120, 214),
}
_ORDEM_SEVERIDADE = {"alerta": 0, "atencao": 1, "info": 2, "positivo": 3}


def render_destaques(achados: list[dict], titulo: str = "🛡️ Destaques do guardião") -> None:
    """Renderiza os insights do motor `analise.insights` como cards, do mais crítico ao menos."""
    if not achados:
        return
    ordenados = sorted(achados, key=lambda a: _ORDEM_SEVERIDADE.get(a.get("severidade", "info"), 9))
    st.subheader(titulo)
    colunas = st.columns(min(len(ordenados), 2))
    for i, a in enumerate(ordenados):
        r, g, b = _ESTILO_SEVERIDADE.get(a.get("severidade", "info"), _ESTILO_SEVERIDADE["info"])
        # O texto usa **negrito** de markdown; dentro de HTML cru precisa virar <b>.
        texto_html = negrito_para_html(a.get("texto", ""))
        with colunas[i % len(colunas)]:
            st.markdown(
                f"<div style='border-left:6px solid rgb({r},{g},{b});"
                f"background:rgba({r},{g},{b},0.08);padding:12px 16px;margin-bottom:12px;"
                f"border-radius:8px;min-height:96px'>"
                f"<div style='font-size:1.02rem;font-weight:600;margin-bottom:4px'>"
                f"{a.get('icone','')} {a.get('titulo','')}</div>"
                f"<div style='opacity:0.92;line-height:1.4'>{texto_html}</div></div>",
                unsafe_allow_html=True,
            )


@st.cache_data(show_spinner=False)
def populacoes_por_ente(exercicio: int, bimestre: int) -> dict:
    """População de cada ente no período (do próprio RREO). A da União é inconfiável
    na fonte — o motor de insights a descarta."""
    pops = {}
    for chave, info in ENTES_MVP.items():
        try:
            df = baixar_rreo(id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre)
            serie = df["populacao"].dropna() if "populacao" in df else pd.Series(dtype=float)
            pops[info["nome"]] = int(serie.iloc[0]) if not serie.empty else None
        except Exception:
            pops[info["nome"]] = None
    return pops


def enriquecer_com_percentuais(tabela: pd.DataFrame, totais_por_ente: pd.Series) -> pd.DataFrame:
    """Adiciona: % do orçamento total do ente e % de execução (realizado / previsão atualizada),
    já com status (ícone + rótulo) classificado a partir do % de execução.
    """
    df = tabela.copy()
    df["proporcao"] = df.apply(
        lambda linha: (linha["realizado"] / totais_por_ente[linha["ente"]]) if totais_por_ente.get(linha["ente"]) else None,
        axis=1,
    )
    df["pct_execucao"] = df.apply(
        lambda linha: (linha["realizado"] / linha["previsao_atualizada"]) if linha["previsao_atualizada"] else None,
        axis=1,
    )
    status = df["pct_execucao"].map(classificar_execucao)
    df["status_icone"] = status.map(lambda s: s["icone"])
    df["status_rotulo"] = status.map(lambda s: s["rotulo"])
    return df


@st.cache_data(show_spinner="Carregando dados do SICONFI...")
def carregar_dados(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache local) o RREO-Anexo 02 de todos os entes do MVP e normaliza.

    Retorna a tabela normalizada, a lista de entes sem dado declarado no período e
    metadados de cada ente (linhas brutas baixadas, data da última sincronização).
    A API do SICONFI já teve instabilidades; se uma chamada falhar, o ente entra
    na lista de "sem dado" em vez de derrubar o app inteiro.
    """
    dados_por_ente = {}
    entes_sem_dado = []
    metadados_entes = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre)
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}
        metadados_entes.append(
            {
                "ente": info["nome"],
                "linhas_brutas": len(df_bruto),
                "atualizado_em": data_atualizacao(info["id_ente"], exercicio, bimestre),
            }
        )

    tabela = normalizar_varios(dados_por_ente)
    return tabela, entes_sem_dado, metadados_entes


@st.cache_data(show_spinner="Carregando receita do SICONFI...")
def carregar_receita(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache) o RREO-Anexo 01 (receita) de todos os entes e normaliza.

    Retorna a tabela de receita por categoria e a lista de entes sem dado no período.
    Mesmo padrão resiliente de `carregar_dados`: falha de um ente não derruba o app.
    """
    dados_por_ente = {}
    entes_sem_dado = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(
                id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre, anexo=ANEXO_RECEITA
            )
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}

    tabela = normalizar_receita_varios(dados_por_ente)
    return tabela, entes_sem_dado


@st.cache_data(show_spinner="Carregando restos a pagar por Poder...")
def carregar_restos_poder(exercicio: int, bimestre: int):
    """Baixa (ou lê do cache) o RREO-Anexo 07 de todos os entes e normaliza por Poder.

    Retorna a tabela [ente, nivel, poder, restos_a_pagar] e a lista de entes sem dado.
    Mesmo padrão resiliente das demais cargas.
    """
    dados_por_ente = {}
    entes_sem_dado = []

    for chave, info in ENTES_MVP.items():
        try:
            df_bruto = baixar_rreo(
                id_ente=info["id_ente"], exercicio=exercicio, bimestre=bimestre, anexo=ANEXO_RESTOS_A_PAGAR
            )
        except Exception:
            df_bruto = pd.DataFrame()

        if df_bruto.empty:
            entes_sem_dado.append(info["nome"])

        dados_por_ente[chave] = {"df": df_bruto, "nome": info["nome"], "nivel": info["nivel"]}

    tabela = normalizar_restos_varios(dados_por_ente)
    return tabela, entes_sem_dado


@st.cache_data(show_spinner="Consultando contratos no PNCP...")
def carregar_contratos(cnpj: str, ano: int):
    """Baixa (ou lê do cache) e normaliza os contratos de um órgão (CNPJ) no ano.

    Retorna (tabela_normalizada, erro) — `erro` é None em caso de sucesso ou uma
    mensagem curta se a consulta ao PNCP falhar.
    """
    from extract.pncp import baixar_contratos
    from transform.contratos import normalizar_contratos

    try:
        bruto = baixar_contratos(cnpj=cnpj, ano=ano)
    except Exception as exc:
        return normalizar_contratos(pd.DataFrame()), f"Falha ao consultar o PNCP: {type(exc).__name__}"
    return normalizar_contratos(bruto), None


@st.cache_data(show_spinner=False)
def carregar_selic(ano_inicial: int, ano_final: int) -> dict:
    """Selic média anual (% a.a.) via Banco Central. Cacheada; {} se a API falhar."""
    from extract.bcb import selic_media_anual

    return selic_media_anual(ano_inicial, ano_final)


@st.cache_data(show_spinner="Montando série por bimestre...")
def serie_despesa_no_bimestre(anos: tuple[int, ...], bimestre: int) -> pd.DataFrame:
    """Despesa realizada total por ente, num bimestre fixo, para cada ano.

    Serve à projeção: comparar o mesmo bimestre entre anos revela a sazonalidade.
    Retorna colunas: ente, ano, realizado.
    """
    linhas = []
    for ano in anos:
        tabela, _, _ = carregar_dados(ano, bimestre)
        if tabela.empty:
            continue
        for ente, val in tabela.groupby("ente")["realizado"].sum().items():
            linhas.append({"ente": ente, "ano": ano, "realizado": float(val)})
    return pd.DataFrame(linhas, columns=["ente", "ano", "realizado"])


@st.cache_data(show_spinner="Montando as séries para os estudos econométricos...")
def series_para_estudos(anos: tuple[int, ...], ano_referencia: int) -> dict:
    """Payload único com tudo que os estudos econométricos precisam.

    Evita que cada estudo recarregue os mesmos dados. Retorna:
      despesa_por_ente / receita_por_ente : {ente: {ano: valor nominal}}
      crescimento_real_por_ente           : {ente: {ano: variação real}}
      niveis, populacoes, selic
      despesa_ref / receita_ref           : tabelas detalhadas do ano de referência
      peso_encargos_uniao                 : {ano: fração da despesa federal}
    """
    from extract.inflacao import fatores_para_base, indice_ipca_anual
    from transform.fiscal import FUNCAO_ENCARGOS

    fatores = fatores_para_base(indice_ipca_anual(max(anos)), max(anos))
    despesa, receita, niveis, populacoes = {}, {}, {}, {}
    peso_encargos_uniao = {}
    despesa_ref, receita_ref = [], []

    for ano in sorted(anos):
        tabela_d, _, _ = carregar_dados(ano, 6)
        tabela_r, _ = carregar_receita(ano, 6)
        if not tabela_d.empty:
            for (ente, nivel), sub in tabela_d.groupby(["ente", "nivel"]):
                total = float(sub["realizado"].sum())
                if total <= 0:
                    continue
                despesa.setdefault(ente, {})[ano] = total
                niveis[ente] = nivel
                if ente == "União":
                    enc = float(sub[sub["funcao"] == FUNCAO_ENCARGOS]["realizado"].sum())
                    peso_encargos_uniao[ano] = enc / total
            if ano == ano_referencia:
                despesa_ref.append(tabela_d)
        if not tabela_r.empty:
            for ente, sub in tabela_r.groupby("ente"):
                total = float(sub["realizada"].sum())
                if total > 0:
                    receita.setdefault(ente, {})[ano] = total
            if ano == ano_referencia:
                receita_ref.append(tabela_r)

    # Crescimento REAL (deflacionado) ano a ano — insumo do teste de ciclo político.
    crescimento = {}
    for ente, serie in despesa.items():
        anos_ord = sorted(serie)
        for i in range(1, len(anos_ord)):
            atual, anterior = anos_ord[i], anos_ord[i - 1]
            v_ant = serie[anterior] * fatores.get(anterior, 1)
            v_atual = serie[atual] * fatores.get(atual, 1)
            if v_ant:
                crescimento.setdefault(ente, {})[atual] = v_atual / v_ant - 1

    pops = {e: p for e, p in populacoes_por_ente(ano_referencia, 6).items()
            if p and niveis.get(e) != "federal"}

    return {
        "despesa_por_ente": despesa,
        "receita_por_ente": receita,
        "crescimento_real_por_ente": crescimento,
        "niveis": niveis,
        "populacoes": pops,
        "selic": carregar_selic(min(anos), max(anos)),
        "peso_encargos_uniao": peso_encargos_uniao,
        "despesa_ref": pd.concat(despesa_ref) if despesa_ref else pd.DataFrame(),
        "receita_ref": pd.concat(receita_ref) if receita_ref else pd.DataFrame(),
        "ano_referencia": ano_referencia,
    }


@st.cache_data(show_spinner="Projetando o fechamento do ano...")
def projecoes_fechamento(anos_hist: tuple[int, ...], ano_corrente: int, bim_atual: int) -> dict:
    """Projeção de fechamento do ano corrente por ente (anualização por sazonalidade).

    Retorna {ente: {projecao, minimo, maximo, erro, fechado_anterior}}. Vazio se o ano
    já fechou (bim_atual>=6) ou não há histórico. Usado pela Home e pela aba Tendências.
    """
    from analise.projecao import erro_backtest, fracao_executada, projetar_ano

    if bim_atual >= 6 or not anos_hist:
        return {}
    parcial_hist = serie_despesa_no_bimestre(anos_hist, bim_atual)
    fechado_hist = serie_despesa_no_bimestre(anos_hist, 6)
    parcial_atual = serie_despesa_no_bimestre((ano_corrente,), bim_atual)

    resultado = {}
    for ente in parcial_atual["ente"].unique():
        parciais = dict(zip(
            parcial_hist[parcial_hist["ente"] == ente]["ano"], parcial_hist[parcial_hist["ente"] == ente]["realizado"]))
        fechados = dict(zip(
            fechado_hist[fechado_hist["ente"] == ente]["ano"], fechado_hist[fechado_hist["ente"] == ente]["realizado"]))
        saz = fracao_executada(parciais, fechados)
        atual = parcial_atual[parcial_atual["ente"] == ente]["realizado"]
        if saz["media"] and not atual.empty:
            proj = projetar_ano(float(atual.iloc[0]), saz)
            resultado[ente] = {
                **proj,
                "erro": erro_backtest(parciais, fechados),
                "fechado_anterior": fechados.get(max(fechados)) if fechados else None,
            }
    return resultado


@st.cache_data(show_spinner=False)
def fatores_ipca(ano_base: int) -> dict:
    """Fatores de deflação (nominal→real em reais do ano-base) por ano, via IPCA/IBGE.

    Cacheado para não consultar a SIDRA a cada rerun.
    """
    from extract.inflacao import fatores_para_base, indice_ipca_anual

    return fatores_para_base(indice_ipca_anual(ano_base), ano_base)


@st.cache_data(show_spinner=False)
def bimestre_recente_uniao(exercicio: int) -> int:
    """Último bimestre publicado pela União no exercício (fallback = 6).

    Serve de default sensato para o ano corrente, cujo fechamento (6º bimestre)
    ainda não saiu. Cacheado para não sondar a API a cada rerun.
    """
    id_uniao = ENTES_MVP["uniao"]["id_ente"]
    bimestre = ultimo_bimestre_publicado(id_uniao, exercicio)
    return bimestre if bimestre is not None else 6


@st.cache_data(show_spinner="Montando série histórica de despesa...")
def serie_anual_despesa(anos: tuple[int, ...]) -> pd.DataFrame:
    """Total de despesa por ente para cada ano da série.

    Para anos fechados usa o acumulado do 6º bimestre; para o ano corrente usa o
    último bimestre publicado (marcado como `parcial=True`, pois não é comparável
    a um ano inteiro). Valores são NOMINAIS (não ajustados por inflação).
    """
    linhas = []
    for ano in anos:
        bim = bimestre_recente_uniao(ano)
        tabela, _, _ = carregar_dados(ano, bim)
        if tabela.empty:
            continue
        agg = tabela.groupby(["ente", "nivel"], as_index=False)[
            ["previsao_inicial", "previsao_atualizada", "realizado"]
        ].sum()
        agg["ano"] = ano
        agg["bimestre"] = bim
        agg["parcial"] = bim < 6
        linhas.append(agg)
    colunas = ["ente", "nivel", "ano", "bimestre", "parcial", "previsao_inicial", "previsao_atualizada", "realizado"]
    if not linhas:
        return pd.DataFrame(columns=colunas)
    return pd.concat(linhas, ignore_index=True)[colunas]


@st.cache_data(show_spinner="Montando série de pesos por função...")
def serie_peso_funcao(anos: tuple[int, ...], funcoes: tuple[str, ...]) -> pd.DataFrame:
    """Fatia (%) da despesa de cada ente nas funções dadas, ano a ano.

    Retorna: ente, nivel, ano, funcao, realizado, total_ente, peso, parcial.
    Usa o cache de despesa (Anexo 02) já aquecido pela série histórica.
    """
    colunas = ["ente", "nivel", "ano", "funcao", "realizado", "total_ente", "peso", "parcial"]
    linhas = []
    for ano in anos:
        bim = bimestre_recente_uniao(ano)
        tabela, _, _ = carregar_dados(ano, bim)
        if tabela.empty:
            continue
        total = tabela.groupby("ente")["realizado"].sum()
        sub = (
            tabela[tabela["funcao"].isin(funcoes)]
            .groupby(["ente", "nivel", "funcao"], as_index=False)["realizado"].sum()
        )
        if sub.empty:
            continue
        sub["ano"] = ano
        sub["total_ente"] = sub["ente"].map(total)
        sub["peso"] = sub.apply(
            lambda r: (r["realizado"] / r["total_ente"]) if r["total_ente"] else None, axis=1
        )
        sub["parcial"] = bim < 6
        linhas.append(sub)
    if not linhas:
        return pd.DataFrame(columns=colunas)
    return pd.concat(linhas, ignore_index=True)[colunas]


@st.cache_data(show_spinner="Montando série histórica de receita...")
def serie_anual_receita(anos: tuple[int, ...]) -> pd.DataFrame:
    """Total de receita realizada por ente para cada ano (mesma lógica de série da despesa)."""
    from transform.receita import totais_receita_por_ente

    linhas = []
    for ano in anos:
        bim = bimestre_recente_uniao(ano)
        tabela, _ = carregar_receita(ano, bim)
        if tabela.empty:
            continue
        agg = totais_receita_por_ente(tabela)
        agg["ano"] = ano
        agg["bimestre"] = bim
        agg["parcial"] = bim < 6
        linhas.append(agg)
    colunas = ["ente", "nivel", "ano", "bimestre", "parcial", "previsao_inicial", "previsao_atualizada", "realizada"]
    if not linhas:
        return pd.DataFrame(columns=colunas)
    return pd.concat(linhas, ignore_index=True)[colunas]
