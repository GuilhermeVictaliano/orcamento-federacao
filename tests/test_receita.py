import pandas as pd

from transform.receita import (
    normalizar_receita,
    normalizar_receita_varios,
    totais_receita_por_ente,
)


def _linha(cod_conta, coluna, valor):
    return {"cod_conta": cod_conta, "conta": cod_conta, "coluna": coluna, "valor": valor}


def test_normalizar_receita_pivota_categorias():
    df_bruto = pd.DataFrame(
        [
            _linha("ReceitaTributaria", "PREVISÃO INICIAL", 100.0),
            _linha("ReceitaTributaria", "PREVISÃO ATUALIZADA (a)", 120.0),
            _linha("ReceitaTributaria", "Até o Bimestre (c)", 90.0),
            _linha("TransferenciasCorrentes", "Até o Bimestre (c)", 30.0),
            # linha que NÃO é categoria (é o total): deve ser ignorada para não duplicar
            _linha("ReceitasExcetoIntraOrcamentarias", "Até o Bimestre (c)", 120.0),
            # coluna irrelevante: ignorada
            _linha("ReceitaTributaria", "% (c/a)", 0.75),
        ]
    )

    resultado = normalizar_receita(df_bruto, nome_ente="União", nivel="federal")

    assert set(resultado["categoria"]) == {"Tributária (impostos, taxas)", "Transferências correntes"}
    trib = resultado[resultado["categoria"] == "Tributária (impostos, taxas)"].iloc[0]
    assert trib["ente"] == "União"
    assert trib["nivel"] == "federal"
    assert trib["previsao_inicial"] == 100.0
    assert trib["previsao_atualizada"] == 120.0
    assert trib["realizada"] == 90.0


def test_normalizar_receita_df_vazio():
    resultado = normalizar_receita(pd.DataFrame(), nome_ente="União", nivel="federal")
    assert resultado.empty
    assert list(resultado.columns) == [
        "ente", "nivel", "categoria", "previsao_inicial", "previsao_atualizada", "realizada"
    ]


def test_totais_receita_soma_categorias_por_ente():
    df = pd.DataFrame(
        [_linha("ReceitaTributaria", "Até o Bimestre (c)", 90.0),
         _linha("TransferenciasCorrentes", "Até o Bimestre (c)", 30.0)]
    )
    dados = {"uniao": {"df": df, "nome": "União", "nivel": "federal"}}
    tabela = normalizar_receita_varios(dados)
    totais = totais_receita_por_ente(tabela)
    assert len(totais) == 1
    assert totais.iloc[0]["realizada"] == 120.0
