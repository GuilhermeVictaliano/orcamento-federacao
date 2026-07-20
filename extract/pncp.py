"""Extração de contratos do PNCP (Portal Nacional de Contratações Públicas).

API pública de consulta: https://pncp.gov.br/api/consulta/v1/contratos

LIMITAÇÕES IMPORTANTES (a página deixa explícito ao usuário):
- O único filtro que a API respeita é `cnpjOrgao` (filtros por município/UF são
  ignorados). Portanto consultamos por ÓRGÃO, via CNPJ.
- Um ente grande tem muitos órgãos, cada um com CNPJ próprio; um CNPJ traz só
  aquele órgão. Não existe "todos os contratos do ente" numa consulta só.
- A adesão ao PNCP é parcial e cresceu ao longo do tempo; entes com sistema
  próprio podem publicar pouco. A lista NÃO é exaustiva.

Cache local em Parquet, como no RREO, por (cnpj, ano).
"""

from pathlib import Path

import pandas as pd
import requests

BASE_PNCP = "https://pncp.gov.br/api/consulta/v1"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "pncp"

# Órgãos verificados contra a API (razaoSocial confirmada). CNPJ só de dígitos.
# União não tem CNPJ único (milhares de órgãos), por isso não é pré-cadastrada.
ORGAOS_CONHECIDOS = {
    "São Paulo (capital) — Município": "46395000000139",
    "Campinas — Município": "51885242000140",
    "Sorocaba — Município": "46634044000174",
    "Estado de SP — Sec. da Fazenda e Planejamento": "46377222000129",
}


def caminho_cache(cnpj: str, ano: int) -> Path:
    return CACHE_DIR / f"pncp_contratos_{cnpj}_{ano}.parquet"


def baixar_contratos(cnpj: str, ano: int, forcar_atualizacao: bool = False) -> pd.DataFrame:
    """Contratos de um órgão (por CNPJ) publicados no ano, com cache local.

    Propaga exceção de rede se a API cair e não houver cache; quem chama decide
    como sinalizar na interface.
    """
    caminho = caminho_cache(cnpj, ano)
    if caminho.exists() and not forcar_atualizacao:
        return pd.read_parquet(caminho)

    df = _consultar_contratos_paginado(cnpj, f"{ano}0101", f"{ano}1231")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not df.empty:
        df.to_parquet(caminho, index=False)
    return df


def _consultar_contratos_paginado(cnpj: str, data_inicial: str, data_final: str) -> pd.DataFrame:
    url = f"{BASE_PNCP}/contratos"
    registros = []
    pagina = 1
    while True:
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "cnpjOrgao": cnpj,
            "pagina": pagina,
            "tamanhoPagina": 100,
        }
        resposta = requests.get(url, params=params, timeout=60)
        if resposta.status_code == 422:
            # CNPJ inválido/sem dados no período — trata como vazio, não como erro.
            return pd.DataFrame()
        resposta.raise_for_status()
        dados = resposta.json()

        items = dados.get("data", []) or []
        registros.extend(items)

        total_paginas = dados.get("totalPaginas", 1) or 1
        if pagina >= total_paginas or not items:
            break
        pagina += 1

    return pd.DataFrame(registros)
