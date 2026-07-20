import pandas as pd

from transform.poderes import (
    COD_SALDO_TOTAL,
    COLUNA_SALDO_TOTAL,
    normalizar_restos_por_poder,
    _mapear_poder,
)


def _linha(conta, valor, cod=COD_SALDO_TOTAL, coluna=COLUNA_SALDO_TOTAL):
    return {"conta": conta, "cod_conta": cod, "coluna": coluna, "valor": valor}


def test_mapear_poder_identifica_principais_e_ignora_suborgaos():
    assert _mapear_poder("PODER EXECUTIVO") == "Executivo"
    assert _mapear_poder("PODER LEGISLATIVO") == "Legislativo"
    assert _mapear_poder("PODER JUDICIÁRIO") == "Judiciário"
    assert _mapear_poder("MINISTÉRIO PÚBLICO") == "Ministério Público"
    assert _mapear_poder("DEFENSORIA PÚBLICA") == "Defensoria Pública"
    # sub-órgãos (Title Case) e linhas de total não são Poderes principais
    assert _mapear_poder("Justiça Federal") is None
    assert _mapear_poder("Ministério Público da União") is None
    assert _mapear_poder("TOTAL (III) = (I + II)") is None


def test_mapear_poder_robusto_a_encoding_quebrado():
    # Mesmo com caractere de substituição no lugar do acento, o prefixo maiúsculo casa.
    assert _mapear_poder("PODER JUDICI�RIO") == "Judiciário"
    assert _mapear_poder("MINIST�RIO P�BLICO") == "Ministério Público"


def test_normalizar_restos_por_poder_soma_saldo_total():
    df = pd.DataFrame(
        [
            _linha("PODER EXECUTIVO", 100.0),
            _linha("PODER LEGISLATIVO", 5.0),
            # linha de outra coluna: ignorada
            _linha("PODER EXECUTIVO", 999.0, coluna="Pagos (c)"),
            # sub-órgão: ignorado
            _linha("Justiça Federal", 3.0),
            # intra (cod diferente): ignorado
            _linha("PODER EXECUTIVO", 7.0, cod="SaldoTotalIntra"),
        ]
    )
    resultado = normalizar_restos_por_poder(df, nome_ente="União", nivel="federal").set_index("poder")
    assert resultado.loc["Executivo", "restos_a_pagar"] == 100.0
    assert resultado.loc["Legislativo", "restos_a_pagar"] == 5.0
    assert "Judiciário" not in resultado.index


def test_normalizar_restos_df_vazio():
    resultado = normalizar_restos_por_poder(pd.DataFrame(), "União", "federal")
    assert resultado.empty
    assert list(resultado.columns) == ["ente", "nivel", "poder", "restos_a_pagar"]
