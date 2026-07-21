"""Paleta categórica fixa para os entes do MVP — ordem fixa, nunca cíclica.

Fonte: paleta categórica validada (contraste + separação para daltonismo) do
skill de visualização de dados.
"""

import pandas as pd

from extract.config import ENTES_MVP

# Paleta categórica (contraste + separação para daltonismo). Estendida para
# comportar mais entes; cores adicionais escolhidas em matizes distintos.
_PALETA_CATEGORICA = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#c65999", "#8c613c"]

ORDEM_ENTES = [info["nome"] for info in ENTES_MVP.values()]

CORES_POR_ENTE = dict(zip(ORDEM_ENTES, _PALETA_CATEGORICA))

COR_PREVISTO = _PALETA_CATEGORICA[0]
COR_REALIZADO = _PALETA_CATEGORICA[1]

# Paleta de status (execução do orçamento) — reservada, nunca reaproveitada
# para identidade de ente/categoria. Sempre acompanhada de ícone + rótulo.
STATUS_EXECUCAO = {
    "alta": {"icone": "🟢", "rotulo": "Execução alta", "cor": "#0ca30c"},
    "parcial": {"icone": "🟡", "rotulo": "Execução parcial", "cor": "#fab219"},
    "baixa": {"icone": "🔴", "rotulo": "Execução baixa", "cor": "#d03b3b"},
    "indefinida": {"icone": "⚪", "rotulo": "Sem dado", "cor": "#898781"},
}


def classificar_execucao(pct) -> dict:
    """Classifica o % de execução (realizado / previsão atualizada) num status fixo."""
    if pct is None or pd.isna(pct):
        return STATUS_EXECUCAO["indefinida"]
    if pct >= 0.90:
        return STATUS_EXECUCAO["alta"]
    if pct >= 0.60:
        return STATUS_EXECUCAO["parcial"]
    return STATUS_EXECUCAO["baixa"]
