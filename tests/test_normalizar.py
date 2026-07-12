import pandas as pd

from transform.normalizar import normalizar_rreo, normalizar_varios


def _linha(rotulo, conta, coluna, valor):
    return {
        "exercicio": 2024,
        "rotulo": rotulo,
        "conta": conta,
        "coluna": coluna,
        "valor": valor,
    }


def test_normalizar_rreo_pivota_previsto_e_realizado():
    df_bruto = pd.DataFrame(
        [
            _linha("Total das Despesas Exceto Intra-Orçamentárias", "Saúde", "DOTAÇÃO INICIAL", 100.0),
            _linha("Total das Despesas Exceto Intra-Orçamentárias", "Saúde", "DOTAÇÃO ATUALIZADA (a)", 110.0),
            _linha("Total das Despesas Exceto Intra-Orçamentárias", "Saúde", "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)", 90.0),
            # subfunção de Saúde: não é função oficial, deve ser descartada
            _linha("Total das Despesas Exceto Intra-Orçamentárias", "Atenção Básica", "DOTAÇÃO INICIAL", 40.0),
            # intra-orçamentária: deve ser descartada para não duplicar
            _linha("Total das Despesas Intra-Orçamentárias", "Saúde", "DOTAÇÃO INICIAL", 5.0),
        ]
    )

    resultado = normalizar_rreo(df_bruto, nome_ente="São Paulo (capital)", nivel="municipal")

    assert len(resultado) == 1
    linha = resultado.iloc[0]
    assert linha["ente"] == "São Paulo (capital)"
    assert linha["nivel"] == "municipal"
    assert linha["funcao"] == "Saúde"
    assert linha["previsao_inicial"] == 100.0
    assert linha["previsao_atualizada"] == 110.0
    assert linha["realizado"] == 90.0


def test_normalizar_rreo_df_vazio_retorna_tabela_vazia():
    resultado = normalizar_rreo(pd.DataFrame(), nome_ente="União", nivel="federal")
    assert resultado.empty
    assert list(resultado.columns) == [
        "ente",
        "nivel",
        "funcao",
        "previsao_inicial",
        "previsao_atualizada",
        "realizado",
    ]


def test_normalizar_varios_concatena_entes():
    df_uniao = pd.DataFrame(
        [_linha("Total das Despesas Exceto Intra-Orçamentárias", "Educação", "DOTAÇÃO INICIAL", 1000.0)]
    )
    df_municipio = pd.DataFrame(
        [_linha("Total das Despesas Exceto Intra-Orçamentárias", "Educação", "DOTAÇÃO INICIAL", 50.0)]
    )

    dados = {
        "uniao": {"df": df_uniao, "nome": "União", "nivel": "federal"},
        "sp_capital": {"df": df_municipio, "nome": "São Paulo (capital)", "nivel": "municipal"},
    }

    resultado = normalizar_varios(dados)

    assert len(resultado) == 2
    assert set(resultado["ente"]) == {"União", "São Paulo (capital)"}
