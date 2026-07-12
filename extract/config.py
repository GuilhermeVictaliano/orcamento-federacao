"""Configurações fixas do MVP: entes cobertos, URLs e parâmetros do SICONFI."""

BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"

# id_ente (cod_ibge) dos entes do MVP, confirmados manualmente contra o endpoint /entes.
# Fora do MVP, novos entes devem ser resolvidos via extract.entes.buscar_entes(),
# nunca fixados diretamente aqui.
ENTES_MVP = {
    "uniao": {"id_ente": 1, "nivel": "federal", "nome": "União"},
    "sp_estado": {"id_ente": 35, "nivel": "estadual", "nome": "Estado de São Paulo"},
    "sp_capital": {"id_ente": 3550308, "nivel": "municipal", "nome": "São Paulo (capital)"},
    "sorocaba": {"id_ente": 3552205, "nivel": "municipal", "nome": "Sorocaba"},
    "campinas": {"id_ente": 3509502, "nivel": "municipal", "nome": "Campinas"},
}

ANEXO_DESPESA_POR_FUNCAO = "RREO-Anexo 02"

# Nomes de coluna do RREO-Anexo 02 usados na transformação (previsto x executado).
# "Realizado" usa despesas LIQUIDADAS (não apenas empenhadas), por ser a medida
# padrão de execução orçamentária no Brasil: exige que o bem/serviço já tenha
# sido entregue, não apenas reservado no orçamento.
COLUNA_PREVISAO_INICIAL = "DOTAÇÃO INICIAL"
COLUNA_PREVISAO_ATUALIZADA = "DOTAÇÃO ATUALIZADA (a)"
COLUNA_REALIZADO = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)"
