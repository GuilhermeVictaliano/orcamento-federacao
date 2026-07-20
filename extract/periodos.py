"""Períodos de análise: anos disponíveis na série do SICONFI e mapeamento
ano → mandato (período de governo de quatro anos).

A União e os estados compartilham o mesmo calendário eleitoral; os municípios
têm calendário deslocado em dois anos. Por isso o mandato de um mesmo ano
depende do nível do ente.
"""

from datetime import date

# Início da série do RREO padronizada e disponível na API do SICONFI.
PRIMEIRO_ANO = 2015

# Janelas de mandato (anos inclusivos) por calendário eleitoral.
# Federal/estadual: eleições em 2014, 2018, 2022, 2026... (posse no ano seguinte).
# Municipal: eleições em 2012, 2016, 2020, 2024... (posse no ano seguinte).
MANDATOS_FEDERAL_ESTADUAL = [
    (2011, 2014),
    (2015, 2018),
    (2019, 2022),
    (2023, 2026),
    (2027, 2030),
]
MANDATOS_MUNICIPAL = [
    (2013, 2016),
    (2017, 2020),
    (2021, 2024),
    (2025, 2028),
    (2029, 2032),
]


def ano_corrente() -> int:
    return date.today().year


def anos_disponiveis(ate: int | None = None) -> list[int]:
    """Anos com dado na API, do mais recente para o mais antigo (2015 → ano corrente)."""
    ano_final = ate if ate is not None else ano_corrente()
    return list(range(ano_final, PRIMEIRO_ANO - 1, -1))


def _mandatos_do_nivel(nivel: str) -> list[tuple[int, int]]:
    return MANDATOS_MUNICIPAL if nivel == "municipal" else MANDATOS_FEDERAL_ESTADUAL


def mandato_do_ano(ano: int, nivel: str) -> tuple[int, int] | None:
    """Janela (inicio, fim) do mandato que contém `ano` para o nível dado; None se fora."""
    for inicio, fim in _mandatos_do_nivel(nivel):
        if inicio <= ano <= fim:
            return (inicio, fim)
    return None


def rotulo_mandato(inicio: int, fim: int) -> str:
    return f"{inicio}–{fim}"


def anos_do_mandato(inicio: int, fim: int, ate: int | None = None) -> list[int]:
    """Anos de um mandato que já ocorreram (não passa do ano corrente / limite `ate`)."""
    ano_final = ate if ate is not None else ano_corrente()
    return [ano for ano in range(inicio, fim + 1) if ano <= ano_final]


def mandatos_disponiveis(nivel: str, ate: int | None = None) -> list[tuple[int, int]]:
    """Mandatos do nível que têm ao menos um ano dentro da série disponível (>= 2015)."""
    ano_final = ate if ate is not None else ano_corrente()
    janelas = []
    for inicio, fim in _mandatos_do_nivel(nivel):
        # Mandato entra se qualquer ano seu cai no intervalo [PRIMEIRO_ANO, ano_final].
        if fim >= PRIMEIRO_ANO and inicio <= ano_final:
            janelas.append((inicio, fim))
    return janelas
