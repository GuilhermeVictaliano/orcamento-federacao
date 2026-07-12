"""Classificação oficial de funções de governo (Portaria MOG nº 42/1999, Anexo I).

O RREO-Anexo 02 devolve função e subfunção misturadas na mesma coluna `conta`,
sem um campo que distinga o nível hierárquico. Usamos esta lista fixa (as 28
funções oficiais) para filtrar só as linhas de função, ignorando as subfunções
que aparecem logo abaixo de cada uma no relatório.
"""

FUNCOES_GOVERNO = [
    "Legislativa",
    "Judiciária",
    "Essencial à Justiça",
    "Administração",
    "Defesa Nacional",
    "Segurança Pública",
    "Relações Exteriores",
    "Assistência Social",
    "Previdência Social",
    "Saúde",
    "Trabalho",
    "Educação",
    "Cultura",
    "Direitos da Cidadania",
    "Urbanismo",
    "Habitação",
    "Saneamento",
    "Gestão Ambiental",
    "Ciência e Tecnologia",
    "Agricultura",
    "Organização Agrária",
    "Indústria",
    "Comércio e Serviços",
    "Comunicações",
    "Energia",
    "Transporte",
    "Desporto e Lazer",
    "Encargos Especiais",
]

# Só contamos despesas "exceto intra-orçamentárias": as intra-orçamentárias são
# transferências entre órgãos do mesmo ente e contá-las junto duplicaria valores.
ROTULO_DESPESA_LIQUIDA = "Total das Despesas Exceto Intra-Orçamentárias"
