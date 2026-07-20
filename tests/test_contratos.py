import pandas as pd

from transform.contratos import normalizar_contratos, resumo_contratos


def _contrato(objeto, valor, fornecedor="ACME LTDA", cnpj="46395000000139", ano=2024, seq=1):
    return {
        "objetoContrato": objeto,
        "nomeRazaoSocialFornecedor": fornecedor,
        "niFornecedor": "12345678000199",
        "valorGlobal": valor,
        "valorInicial": valor,
        "dataAssinatura": "2024-03-01",
        "dataVigenciaInicio": "2024-03-01",
        "dataVigenciaFim": "2025-03-01",
        "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": "MUNICIPIO DE SAO PAULO"},
        "unidadeOrgao": {"nomeUnidade": "Secretaria X"},
        "anoContrato": ano,
        "sequencialContrato": seq,
    }


def test_normalizar_ordena_por_valor_desc_e_monta_link():
    df = pd.DataFrame([_contrato("Objeto barato", 100.0, seq=1), _contrato("Objeto caro", 5000.0, seq=2)])
    out = normalizar_contratos(df)
    assert list(out["valor_global"]) == [5000.0, 100.0]  # ordenado desc
    assert out.iloc[0]["objeto"] == "Objeto caro"
    assert out.iloc[0]["orgao"] == "MUNICIPIO DE SAO PAULO"
    assert out.iloc[0]["unidade"] == "Secretaria X"
    assert out.iloc[0]["link"] == "https://pncp.gov.br/app/contratos/46395000000139/2024/2"


def test_normalizar_df_vazio():
    out = normalizar_contratos(pd.DataFrame())
    assert out.empty
    assert "valor_global" in out.columns


def test_resumo_contratos():
    df = pd.DataFrame([_contrato("A", 100.0, seq=1), _contrato("B", 300.0, seq=2)])
    out = normalizar_contratos(df)
    r = resumo_contratos(out)
    assert r["quantidade"] == 2
    assert r["valor_total"] == 400.0
    assert r["maior"] == 300.0


def test_resumo_vazio():
    r = resumo_contratos(normalizar_contratos(pd.DataFrame()))
    assert r == {"quantidade": 0, "valor_total": 0.0, "maior": 0.0}
