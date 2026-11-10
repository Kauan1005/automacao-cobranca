"""Normalização de celulares brasileiros para o formato aceito pelas APIs de mensagem (55 + DDD + número)."""

from __future__ import annotations

from .documentos import so_digitos

DDDS_VALIDOS = frozenset(
    {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46,
     47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85,
     86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99}
)


def normalizar_celular(valor: str | int | None) -> str | None:
    """Devolve o celular como '55DDD9XXXXXXXX' ou None se não for um celular válido.

    Aceita entradas com ou sem 55, com ou sem o zero de operadora e com pontuação.

    >>> normalizar_celular("(11) 98765-4321")
    '5511987654321'
    """
    d = so_digitos(valor).lstrip("0")
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 10 and d[2] in "6789":  # celular antigo sem o 9 na frente
        d = d[:2] + "9" + d[2:]
    if len(d) != 11 or d[2] != "9":
        return None
    if int(d[:2]) not in DDDS_VALIDOS or d[3:] == d[3] * 8:
        return None
    return "55" + d


def ddd(celular: str) -> int:
    """DDD de um celular já normalizado."""
    return int(celular[2:4])
