"""Segmentação por faixa de atraso e escolha do canal de envio."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .limpeza import Contato

# (dias mínimos, dias máximos, faixa, canal) — valores de exemplo
FAIXAS: tuple[tuple[int, int, str, str], ...] = (
    (0, 4, "AVISO", "RCS"),
    (5, 30, "05 a 30", "WHATSAPP"),
    (31, 120, "31 a 120", "WHATSAPP"),
    (121, 990, "121 a 990", "WHATSAPP"),
)


@dataclass(frozen=True)
class Segmento:
    faixa: str
    canal: str


def segmento_de(dias_atraso: int) -> Segmento | None:
    """Faixa e canal para um atraso; None quando o contrato está fora da régua de cobrança."""
    for minimo, maximo, faixa, canal in FAIXAS:
        if minimo <= dias_atraso <= maximo:
            return Segmento(faixa, canal)
    return None


def segmentar(contatos: list[Contato]) -> dict[Segmento, list[Contato]]:
    """Agrupa os contatos por segmento, do maior valor em aberto para o menor (prioridade de envio)."""
    grupos: dict[Segmento, list[Contato]] = defaultdict(list)
    for c in contatos:
        seg = segmento_de(c.dias_atraso)
        if seg:
            grupos[seg].append(c)
    for lista in grupos.values():
        lista.sort(key=lambda c: c.valor_aberto, reverse=True)
    return dict(grupos)
