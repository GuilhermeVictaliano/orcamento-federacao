"""Normaliza contratos brutos do PNCP numa tabela enxuta e auditável.

Objetivo: expor os contratos para o usuário inspecionar (ordenar por valor, ler o
objeto, ver o fornecedor e abrir o registro oficial no PNCP). NÃO julgamos se um
contrato é "superfaturado" — quem audita é a pessoa.
"""

import pandas as pd

COLUNAS_SAIDA = [
    "objeto", "fornecedor", "ni_fornecedor", "valor_global", "valor_inicial",
    "data_assinatura", "vigencia_inicio", "vigencia_fim", "orgao", "unidade", "link",
]


def _campo_dict(valor, chave):
    return valor.get(chave) if isinstance(valor, dict) else None


def _link_pncp(linha) -> str | None:
    orgao = linha.get("orgaoEntidade")
    cnpj = _campo_dict(orgao, "cnpj")
    ano = linha.get("anoContrato")
    seq = linha.get("sequencialContrato")
    if cnpj and ano and seq is not None:
        return f"https://pncp.gov.br/app/contratos/{cnpj}/{ano}/{seq}"
    return None


def normalizar_contratos(df_bruto: pd.DataFrame) -> pd.DataFrame:
    """Converte o JSON do PNCP numa tabela enxuta, ordenada por valor decrescente."""
    if df_bruto.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df = df_bruto
    out = pd.DataFrame(
        {
            "objeto": df.get("objetoContrato"),
            "fornecedor": df.get("nomeRazaoSocialFornecedor"),
            "ni_fornecedor": df.get("niFornecedor"),
            "valor_global": pd.to_numeric(df.get("valorGlobal"), errors="coerce"),
            "valor_inicial": pd.to_numeric(df.get("valorInicial"), errors="coerce"),
            "data_assinatura": df.get("dataAssinatura"),
            "vigencia_inicio": df.get("dataVigenciaInicio"),
            "vigencia_fim": df.get("dataVigenciaFim"),
            "orgao": df.get("orgaoEntidade").map(lambda o: _campo_dict(o, "razaoSocial")) if "orgaoEntidade" in df else None,
            "unidade": df.get("unidadeOrgao").map(lambda o: _campo_dict(o, "nomeUnidade")) if "unidadeOrgao" in df else None,
            "link": df.apply(_link_pncp, axis=1),
        }
    )
    return out.sort_values("valor_global", ascending=False, na_position="last").reset_index(drop=True)[COLUNAS_SAIDA]


def resumo_contratos(tabela: pd.DataFrame) -> dict:
    """Estatísticas de topo para os cards: nº de contratos, valor total, maior contrato."""
    if tabela.empty:
        return {"quantidade": 0, "valor_total": 0.0, "maior": 0.0}
    return {
        "quantidade": int(len(tabela)),
        "valor_total": float(tabela["valor_global"].sum(skipna=True)),
        "maior": float(tabela["valor_global"].max(skipna=True)),
    }
