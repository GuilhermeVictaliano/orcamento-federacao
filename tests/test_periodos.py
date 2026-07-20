from extract import periodos


def test_anos_disponiveis_ordem_decrescente_ate_2015():
    anos = periodos.anos_disponiveis(ate=2026)
    assert anos[0] == 2026
    assert anos[-1] == 2015
    assert anos == sorted(anos, reverse=True)
    assert 2015 in anos and 2020 in anos


def test_mandato_do_ano_federal_estadual():
    assert periodos.mandato_do_ano(2024, "federal") == (2023, 2026)
    assert periodos.mandato_do_ano(2024, "estadual") == (2023, 2026)
    assert periodos.mandato_do_ano(2019, "federal") == (2019, 2022)
    assert periodos.mandato_do_ano(2018, "federal") == (2015, 2018)


def test_mandato_do_ano_municipal_deslocado():
    # Municípios têm calendário deslocado em 2 anos.
    assert periodos.mandato_do_ano(2024, "municipal") == (2021, 2024)
    assert periodos.mandato_do_ano(2025, "municipal") == (2025, 2028)
    assert periodos.mandato_do_ano(2022, "municipal") == (2021, 2024)


def test_anos_do_mandato_nao_passa_do_ano_corrente():
    # Mandato 2023-2026 visto em 2024: só 2023 e 2024 já ocorreram.
    assert periodos.anos_do_mandato(2023, 2026, ate=2024) == [2023, 2024]
    assert periodos.anos_do_mandato(2019, 2022, ate=2024) == [2019, 2020, 2021, 2022]


def test_rotulo_mandato():
    assert periodos.rotulo_mandato(2023, 2026) == "2023–2026"


def test_mandatos_disponiveis_filtra_pela_serie():
    federais = periodos.mandatos_disponiveis("federal", ate=2026)
    assert (2023, 2026) in federais
    assert (2015, 2018) in federais
    # Mandato inteiramente anterior a 2015 não entra.
    assert (2011, 2014) not in federais
