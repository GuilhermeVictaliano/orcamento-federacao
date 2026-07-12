"""Paleta categórica fixa para os entes do MVP — ordem fixa, nunca cíclica.

Fonte: paleta categórica validada (contraste + separação para daltonismo) do
skill de visualização de dados.
"""

from extract.config import ENTES_MVP

_PALETA_CATEGORICA = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7"]

ORDEM_ENTES = [info["nome"] for info in ENTES_MVP.values()]

CORES_POR_ENTE = dict(zip(ORDEM_ENTES, _PALETA_CATEGORICA))

COR_PREVISTO = _PALETA_CATEGORICA[0]
COR_REALIZADO = _PALETA_CATEGORICA[1]
